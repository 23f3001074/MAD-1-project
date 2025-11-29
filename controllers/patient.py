from flask import render_template, request, redirect, url_for, flash, session
from functools import wraps
from database.model import db, Admin, Patient, Doctor, Appointment, Blacklist, Department, Doctor_blacklist,Treatment,DoctorAvailability  # adjust import
from sqlalchemy import or_
from datetime import date, timedelta, datetime as dt



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
        """
        Main patient dashboard route. Shows different partials depending on `role`.
        For 'overview' we query upcoming booked appointments belonging to this patient.
        """

        # 1) Get logged-in patient id from session (set by your login logic)
        patient_id = session.get('user_id')
        if not patient_id:
            flash("Patient not logged in.", "danger")
            return redirect(url_for('login'))  # change to your login endpoint

        # 2) Load patient name for header
        patient = Patient.query.get(patient_id)
        name = patient.full_name if patient else "Patient"

        # 3) Only query appointments for overview (keep other pages light)
        appointments = []
        if role == 'overview':
            today = date.today()
            # Get appointments that are booked and today or in future for this patient
            appointments = (Appointment.query
                            .filter(Appointment.patient_id == patient_id,
                                    Appointment.status == 'booked',
                                    Appointment.date >= today)
                            .join(Doctor)  # optional but helps relationship loading
                            .order_by(Appointment.date.asc(), Appointment.time.asc())
                            .all())

        # 4) Render the patient dashboard template (includes the overview partial)
        return render_template('patient/patient_dashboard.html',
                              name=name, role=role, appointments=appointments)


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