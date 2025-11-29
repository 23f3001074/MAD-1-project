from flask import render_template, request, redirect, url_for, flash, session
from functools import wraps
from database.model import db, Admin, Patient, Doctor, Appointment, Blacklist, Department, Doctor_blacklist,Treatment,DoctorAvailability  # adjust import
from sqlalchemy import or_
from datetime import date, timedelta, datetime as dt
from datetime import datetime, date, timedelta

def generate_slots(start, end):
    slots = []
    cur = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    while cur + timedelta(minutes=20) <= end_dt:
        slots.append(cur.time())
        cur += timedelta(minutes=20)
    return slots

def patient_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.')
            return redirect(url_for('login'))
        if session.get('role') != 'patient':
            flash('Access denied: doctors only.')
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapper

def setup_patient_routes(app):

    @app.route("/patient/dashboard")
    @patient_required
    def patient_dashboard():
        """
        Redirect to the default patient role (overview).
        Keeps URL consistent: /patient/dashboard -> /patient/dashboard/overview
        """
        return redirect(url_for('patient_role_tab', role='overview'))


    @app.route("/patient/dashboard/<role>")
    @patient_required
    def patient_role_tab(role):
        # make sure logged in
        patient_id = session.get('user_id')
        if not patient_id:
            flash("Patient not logged in.", "danger")
            return redirect(url_for('login'))

        # load patient for header
        patient = Patient.query.get(patient_id)
        name = patient.full_name if patient else "Patient"

        # default variables passed to template (avoid undefined in templates)
        appointments = []
        treatments = []
        departments = []

        # overview (upcoming appointments)
        if role == 'overview':
            today = date.today()
            appointments = (Appointment.query
                            .filter(Appointment.patient_id == patient_id,
                                    Appointment.status == 'booked',
                                    Appointment.date >= today)
                            .join(Doctor)
                            .order_by(Appointment.date.asc(), Appointment.time.asc())
                            .all())

        # treatment history
        elif role == 'treatment_history':
            treatments = (Treatment.query
                          .join(Appointment, Treatment.appointment_id == Appointment.appointment_id)
                          .join(Doctor, Appointment.doctor_id == Doctor.doctor_id)
                          .filter(Appointment.patient_id == patient_id)
                          .order_by(Appointment.date.desc(), Appointment.time.desc())
                          .all())

        # book appointment -> load departments so template can render dropdown
        elif role == 'book_appointment':
            # load all departments (ordered by name)
            departments = Department.query.order_by(Department.department_name).all()

            # DEBUG: print to terminal so you can see what was loaded
            print("DEBUG: departments loaded:", [(d.department_id, d.department_name) for d in departments])

        # always pass these into template (keeps template simple)
        return render_template('patient/patient_dashboard.html',
                              name=name,
                              role=role,
                              appointments=appointments,
                              patient=patient,
                              treatments=treatments,
                              departments=departments)

    @app.route("/patient/appointment/cancel/<int:appointment_id>", methods=['POST'])
    @patient_required
    def patient_cancel_appointment(appointment_id):
        """
        Cancel an appointment belonging to the logged-in patient.

        Rules:
        - Only the patient who owns the appointment may cancel it.
        - Only appointments with status 'booked' will be changed to 'cancelled'.
        - Uses POST to avoid accidental cancellations via GET.
        """
        patient_id = session.get('user_id')
        appt = Appointment.query.get(appointment_id)

        if not appt:
            flash("Appointment not found.", "warning")
            return redirect(url_for('patient_role_tab', role='overview'))

        # Authorization check
        if appt.patient_id != patient_id:
            flash("You are not authorized to cancel this appointment.", "danger")
            return redirect(url_for('patient_role_tab', role='overview'))

        # Business rule: only cancel booked appointments
        if appt.status != 'booked':
            flash("Only booked appointments can be cancelled.", "info")
            return redirect(url_for('patient_role_tab', role='overview'))

        try:
            appt.status = 'cancelled'
            db.session.commit()
            flash("Appointment cancelled successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not cancel appointment. Please try again.", "danger")

        return redirect(url_for('patient_role_tab', role='overview'))
    

# ------------------------------------------------------------------------------
# -------------------------------patient----------------------------------------
# ------------------------------------------------------------------------------

    @app.route("/patient/profile", methods=["GET", "POST"])
    @patient_required
    def patient_profile():
        # get logged-in patient id
        pid = session.get("user_id")
        if not pid:
            flash("Please log in.", "warning")
            return redirect(url_for("login"))

        patient = Patient.query.get(pid)
        if not patient:
            flash("Patient not found.", "danger")
            return redirect(url_for("login"))

        if request.method == "POST":
            # update only editable fields
            patient.full_name = request.form.get("full_name", patient.full_name).strip()
            patient.phone_no  = request.form.get("phone_no", patient.phone_no).strip()
            patient.address   = request.form.get("address", patient.address).strip()

            try:
                db.session.commit()
                flash("Profile updated.", "success")
            except Exception:
                db.session.rollback()
                flash("Could not save changes.", "danger")

            # redirect to avoid double submission
            return redirect(url_for("patient_profile"))

        # GET -> render form
        return render_template("patient/patient_dashboard.html", patient=patient, role="profile")
    
    # ------------------------- Book Appointment -----------------------------
    @app.route("/patient/book", methods=["GET", "POST"])
    @patient_required
    def patient_book():
        patient_id = session.get("user_id")

        # Step 1 — show department list
        if request.method == "GET":
            depts = Department.query.all()
            return render_template("patient/parts/book_step1.html", depts=depts)

        # POST – step handling
        step = request.form.get("step")

        # Step 2 — chosen department → show doctors + date field
        if step == "1":
          dept_id = int(request.form["department"])
          doctors = Doctor.query.filter_by(department_id=dept_id).all()

          # If no doctors, show a message and return same page
          if not doctors:
              flash("No doctors available for this department.", "warning")
              return redirect(url_for("patient_role_tab", role="book_appointment"))

          return render_template(
              "patient/parts/book_step2.html",
              dept_id=dept_id,
              doctors=doctors,
              today=date.today()
    )
        # Step 3 — chosen doctor + date → show available slots
        if step == "2":
            dept_id = int(request.form["department"])
            doctor_id = int(request.form["doctor"])
            date_str = request.form["date"]
            d = datetime.strptime(date_str, "%Y-%m-%d").date()

            # load availability row
            av = DoctorAvailability.query.filter_by(doctor_id=doctor_id, date=d).first()
            if not av:
                flash("Doctor not available on this date.", "warning")
                return redirect(url_for("patient_role_tab", role="book_appointment"))

            # morning shift slots
            slots = []
            if av.shift1_enabled:
                start = av.shift1_start or DoctorAvailability.SHIFT1_START
                end = av.shift1_end or DoctorAvailability.SHIFT1_END
                slots += generate_slots(start, end)

            # afternoon shift slots
            if av.shift2_enabled:
                start = av.shift2_start or DoctorAvailability.SHIFT2_START
                end = av.shift2_end or DoctorAvailability.SHIFT2_END
                slots += generate_slots(start, end)

            # Remove booked slots
            booked = Appointment.query.filter_by(
                doctor_id=doctor_id, date=d, status="booked"
            ).all()
            booked_times = {b.time for b in booked}
            available = [t for t in slots if t not in booked_times]

            return render_template("patient/parts/book_step3.html",
                                  dept_id=dept_id,
                                  doctor_id=doctor_id,
                                  date_str=date_str,
                                  slots=available)

        # Step 4 — confirm final booking
        if step == "3":
            dept_id = request.form["department"]
            doctor_id = int(request.form["doctor"])
            date_str = request.form["date"]
            time_str = request.form["time"]

            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            t = datetime.strptime(time_str, "%H:%M").time()

            new_appt = Appointment(
                patient_id=patient_id,
                doctor_id=doctor_id,
                date=d,
                time=t,
                department=Department.query.get(dept_id).department_name,
                status="booked"
            )
            db.session.add(new_appt)
            db.session.commit()

            flash("Appointment booked!", "success")
            return redirect(url_for("patient_role_tab", role="overview"))
        

