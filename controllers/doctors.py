from flask import render_template, request, redirect, url_for, flash, session
from functools import wraps
from database.model import db, Admin, Patient, Doctor, Appointment, Blacklist, Department, Doctor_blacklist,Treatment,DoctorAvailability  # adjust import
from sqlalchemy import or_
from datetime import date, timedelta, datetime as dt



def doctor_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.')
            return redirect(url_for('login'))
        if session.get('role') != 'doctor':
            flash('Access denied: doctors only.')
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapper
# allowed values (validate incoming URL segments)
VALID_ROLES = ("appointments", "patients", "availability")  # use consistent spelling
VALID_STATUSES = ("upcoming", "completed", "cancelled")


def setup_doctor_routes(app):
    """
    Register doctor dashboard routes on the provided Flask `app`.
    Usage: call setup_doctor_routes(app) when building your app.
    """

    @app.route("/doctor/dashboard")
    @doctor_required
    def doctor_dashboard():
        # default landing: appointments with upcoming status
        return redirect(url_for("doctor_role_tab", role="appointments", status="upcoming"))

    # canonical route: /doctor/dashboard/<role>/<status>
    @app.route("/doctor/dashboard/<role>/<status>")
    @doctor_required
    def doctor_role_tab(role, status):
        # normalize and validate
        role = (role or "").lower()
        status = (status or "").lower()

        if role not in VALID_ROLES:
            flash("Unknown tab — showing Appointments.")
            return redirect(url_for("doctor_role_tab", role="appointments", status="upcoming"))

        if status not in VALID_STATUSES:
            flash("Unknown status — showing upcoming.")
            status = "upcoming"

        # fetch current doctor from session
        doctor_id = session.get("user_id")
        this_doctor = Doctor.query.filter_by(doctor_id=doctor_id).first()
        full_name = this_doctor.full_name if this_doctor else "Doctor"

        # minimal role-specific data (expand as needed)
        context = {
            "role": role,
            "status": status,
            "name": full_name,
            "doctor_id": doctor_id
        }

        if role == "appointments":
            if status == "upcoming":
                # earliest upcoming first
                appointments = Appointment.query.filter_by(
                    doctor_id=doctor_id, status="booked"
                ).order_by(Appointment.date.asc(), Appointment.time.asc()).all()
            elif status == "completed":
                # most recent completed first
                appointments = Appointment.query.filter_by(
                    doctor_id=doctor_id, status="completed"
                ).order_by(Appointment.date.desc(), Appointment.time.desc()).all()
            else:  # cancelled
                appointments = Appointment.query.filter_by(
                    doctor_id=doctor_id, status="cancelled"
                ).order_by(Appointment.date.desc(), Appointment.time.desc()).all()

            context["appointments"] = appointments

        elif role == "patients":
            patients = [appt.patient_id for appt in Appointment.query.filter_by(doctor_id=doctor_id).all()]
            context["patients"] = patients

        else:  # availability
            # Build next 7 days
            days = [date.today() + timedelta(days=i) for i in range(7)]

            # Load existing availability rows for this doctor (only one query)
            existing = DoctorAvailability.query.filter_by(doctor_id=doctor_id).all()
            existing_map = {a.date: a for a in existing}

            # Prepare a simple list the template can iterate.
            # NOTE: replaced old start_time/end_time keys with shift1_* and shift2_*
            availability = []
            for d in days:
                row = existing_map.get(d)
                availability.append({
                    "date": d,
                    "key": d.isoformat(),  # used in form names

                    # Morning (shift1)
                    "shift1_enabled": bool(row and getattr(row, "shift1_enabled", False)),
                    "shift1_start": (row.shift1_start.strftime("%H:%M") if row and row.shift1_start else ""),
                    "shift1_end":   (row.shift1_end.strftime("%H:%M") if row and row.shift1_end else ""),

                    # Afternoon (shift2)
                    "shift2_enabled": bool(row and getattr(row, "shift2_enabled", False)),
                    "shift2_start": (row.shift2_start.strftime("%H:%M") if row and row.shift2_start else ""),
                    "shift2_end":   (row.shift2_end.strftime("%H:%M") if row and row.shift2_end else ""),

                    # convenience flag for templates that expect a single 'available' boolean
                    "available": True if row else False
                })

            # add to context so the included partial can render
            context["availability"] = availability

        # render a single dashboard shell that includes partials
        return render_template("doctor/doctor_dashboard.html", **context)

    
    @app.route("/doctor/patient/<int:patient_id>/history")
    @doctor_required
    def doctor_patient_history(patient_id):
        """
        Show a patient's visit history and treatment details for the logged-in doctor.
        - loads visits (appointments) for this doctor+patient
        - loads associated Treatment rows in one additional query
        - builds a mapping appointment_id -> treatment for template use
        """

        doctor_id = session.get("user_id")

        # load patient (adjust patient_id if your model uses a different name)
        patient = Patient.query.filter_by(patient_id=patient_id).first()
        if not patient:
            flash("Patient not found.", "warning")
            return redirect(url_for("doctor_role_tab", role="patients", status="upcoming"))

        # SECURITY: ensure this patient belongs to this doctor (adjust as needed)
        if getattr(patient, "doctor_id", None) is not None and patient.doctor_id != doctor_id:
            flash("Access denied: You are not assigned to this patient.", "danger")
            return redirect(url_for("doctor_role_tab", role="patients", status="upcoming"))

        # Fetch visits/appointments for this patient with this doctor (most recent first)
        visits = Appointment.query.filter_by(patient_id=patient_id, doctor_id=doctor_id) \
                                  .order_by(Appointment.date.desc()).all()

        # If there are visits, fetch their treatments in a single query:
        treatment_map = {}  # appointment_id -> Treatment object (or None)
        if visits:
            appt_ids = [v.appointment_id for v in visits if getattr(v, "appointment_id", None) is not None]
            if appt_ids:
                # single query to fetch all treatments for these appointment IDs
                treatments = Treatment.query.filter(Treatment.appointment_id.in_(appt_ids)).all()
                # map them by appointment_id for fast lookup in template
                treatment_map = {t.appointment_id: t for t in treatments}

        # prepare context and render
        context = {
            "patient": patient,
            "visits": visits,
            "treatment_map": treatment_map,
            "doctor_id": doctor_id,
            "name": getattr(Doctor.query.filter_by(doctor_id=doctor_id).first(), "full_name", "Doctor")
        }
        return render_template("doctor/patient_history.html", **context)
    
    @app.route("/doctor/availability", methods=["GET", "POST"])
    @doctor_required
    def doctor_availability():
        """
        Availability page (next 7 days).
        - Each day has two FIXED shifts:
            Morning  : 09:00 - 12:00  -> checkbox name: shift1_YYYY-MM-DD
            Afternoon: 13:00 - 16:00  -> checkbox name: shift2_YYYY-MM-DD
        - Doctors can only toggle checkboxes (enable/disable shifts).
        - Times are set server-side using model constants (doctors cannot change times).
        """
        doctor_id = session.get("user_id")  # current logged-in doctor

        # next 7 calendar days (today + 6)
        days = [date.today() + timedelta(days=i) for i in range(7)]

        # load existing availability rows for this doctor in a single query
        existing_rows = DoctorAvailability.query.filter_by(doctor_id=doctor_id).all()
        existing_map = {r.date: r for r in existing_rows}  # map date -> DB row

        if request.method == "POST":
            # loop all days and sync checkboxes -> DB
            for d in days:
                key = d.isoformat()                 # e.g. "2025-11-27"
                shift1_on = f"shift1_{key}" in request.form
                shift2_on = f"shift2_{key}" in request.form

                # if both unchecked -> delete DB row (if exists)
                if not shift1_on and not shift2_on:
                    if d in existing_map:
                        db.session.delete(existing_map.pop(d))
                    continue

                # ensure DB row exists
                row = existing_map.get(d)
                if not row:
                    row = DoctorAvailability(doctor_id=doctor_id, date=d)
                    db.session.add(row)
                    existing_map[d] = row

                # set flags & fixed times (do NOT accept posted times)
                row.shift1_enabled = bool(shift1_on)
                if shift1_on:
                    row.shift1_start = DoctorAvailability.SHIFT1_START
                    row.shift1_end   = DoctorAvailability.SHIFT1_END
                else:
                    row.shift1_start = None
                    row.shift1_end   = None

                row.shift2_enabled = bool(shift2_on)
                if shift2_on:
                    row.shift2_start = DoctorAvailability.SHIFT2_START
                    row.shift2_end   = DoctorAvailability.SHIFT2_END
                else:
                    row.shift2_start = None
                    row.shift2_end   = None

            # commit once after processing all days
            try:
                db.session.commit()
                flash("Availability saved.", "success")
            except Exception:
                db.session.rollback()
                flash("Save failed.", "danger")

            return redirect(url_for("doctor_role_tab", role="availability", status="upcoming"))

        # GET: prepare simple data for template (booleans + optional time strings)
        availability = []
        for d in days:
            row = existing_map.get(d)
            availability.append({
                "date": d,
                "key": d.isoformat(),  # used in form field names
                "shift1_enabled": bool(row and getattr(row, "shift1_enabled", False)),
                "shift2_enabled": bool(row and getattr(row, "shift2_enabled", False)),
                # optional readable times (not required for your simple UI)
                "shift1_start": (row.shift1_start.strftime("%H:%M") if row and row.shift1_start else ""),
                "shift1_end":   (row.shift1_end.strftime("%H:%M")   if row and row.shift1_end   else ""),
                "shift2_start": (row.shift2_start.strftime("%H:%M") if row and row.shift2_start else ""),
                "shift2_end":   (row.shift2_end.strftime("%H:%M")   if row and row.shift2_end   else ""),
            })

        return render_template("doctor/parts/availability.html", availability=availability)

