from flask import render_template, request, redirect, url_for, flash, session
from functools import wraps
from database.model import db, Admin, Patient, Doctor, Appointment, Blacklist, Department, Doctor_blacklist  # adjust import
from sqlalchemy import or_


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Access denied: Admins only.')
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapper

def setup_admin_routes(app):

    @app.route("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        # default to "overview"
        return redirect(url_for('admin_role_tab', role='overview'))

    # Note: function name 'admin_role_tab' matches url_for(...) usage in the template
    @app.route("/admin/dashboard/<role>")
    @admin_required
    def admin_role_tab(role):
        # allowed tabs
        valid_roles = ('overview', 'doctors', 'patients', 'appointments')
        if role not in valid_roles:
            flash('Invalid tab.')
            return redirect(url_for('admin_role_tab', role='overview'))

        # search term (only used for doctors/patients)
        q = request.args.get('q', '').strip()
        like = f"%{q}%"

        context = {'role': role, 'q': q}

        if role == 'doctors':
            # search doctors by name or email (only if q present)
            query = Doctor.query
            if q:
                query = query.filter(
                    or_(
                        Doctor.full_name.ilike(like),
                        Doctor.email.ilike(like)
                    )
                )
            context['doctors'] = query.order_by(Doctor.full_name).all()
            context['departments'] = Department.query.all()
            context['doctor_blacklisted_ids'] = Doctor_blacklist.query.all()

        elif role == 'patients':
            # search patients by name, email, or phone (only if q present)
            query = Patient.query
            if q:
                query = query.filter(
                    or_(
                        Patient.full_name.ilike(like),
                        Patient.email.ilike(like),
                        Patient.phone_no.ilike(like)
                    )
                )
            context['patients'] = query.order_by(Patient.full_name).all()
            context['blacklisted_ids'] = Blacklist.query.all()

        elif role == 'appointments':
            # keep previous appointments behavior (no search)
            context['appointments'] = Appointment.query.order_by(Appointment.date.desc()).all()

        else:  # overview
            context['counts'] = {
                'doctors': Doctor.query.count(),
                'patients': Patient.query.count(),
                'appointments': Appointment.query.count(),
                'blacklisted': Blacklist.query.count()
            }
            context['departments'] = Department.query.all()

        return render_template("admin/dashboard.html", **context)

    

# -----------------------------------------------------------------------
# ------------------- Patient Management Routes -------------------------
# -----------------------------------------------------------------------
    # ✅ ---- Delete patient (admin only) ----    
    @app.route("/admin/patient/delete/<int:patient_id>", methods=["POST"])
    @admin_required
    def delete_patient(patient_id):
        """Deletes a patient from the database (admin only)."""
        patient = Patient.query.get(patient_id)

        if not patient:
            flash("Patient not found.", "warning")
            return redirect(url_for("admin_role_tab", role="patients"))

        # Delete the patient record
        db.session.delete(patient)
        db.session.commit()

        flash(f"Patient '{patient.full_name}' has been deleted successfully.", "success")
        return redirect(url_for("admin_role_tab", role="patients"))
    
    # ✅ ---- View patient details (admin only) ----
    @app.route("/admin/patient/<int:patient_id>")
    @admin_required
    def view_patient(patient_id):
        """Displays detailed info for one patient (admin only)."""
        patient = Patient.query.get(patient_id)

        if not patient:
            flash("Patient not found.", "warning")
            return redirect(url_for("admin_role_tab", role="patients"))

        return render_template("admin/patient_detail.html", patient=patient)
    
    # ✅ ---- Unblacklist patient (admin only) ----
    @app.route("/admin/patient/unblacklist/<int:patient_id>", methods=["POST"])
    @admin_required
    def unblacklist_patient(patient_id):
        """
        Removes a patient from the Blacklist table (admin only).
        Triggered when the admin clicks the 'Unblacklist' button.
        """

        # 1️⃣ Look for an existing blacklist record for this patient
        entry = Blacklist.query.filter_by(patient_id=patient_id).first()

        # 2️⃣ If there’s no record, show a message and do nothing
        if not entry:
            flash("This patient is not blacklisted.", "info")
        else:
            # 3️⃣ Delete the record from the table
            db.session.delete(entry)
            db.session.commit()
            flash("Patient has been removed from the blacklist.", "success")

        # 4️⃣ Redirect back to the Patients tab in the admin dashboard
        return redirect(url_for("admin_role_tab", role="patients"))
    
    # ✅ ---- Blacklist patient (admin only) ----
    @app.route("/admin/patient/blacklist/<int:patient_id>", methods=["POST"])
    @admin_required
    def blacklist_patient(patient_id):
        """
        Adds a patient to the Blacklist table (admin only).
        Triggered when the admin clicks the 'Blacklist' button.
        """

        # 1️⃣ Find the patient first
        patient = Patient.query.get(patient_id)
        if not patient:
            flash("Patient not found.", "warning")
            return redirect(url_for("admin_role_tab", role="patients"))

        # 2️⃣ Check if patient already blacklisted
        existing_entry = Blacklist.query.filter_by(patient_id=patient_id).first()
        if existing_entry:
            flash(f"Patient '{patient.full_name}' is already blacklisted.", "info")
            return redirect(url_for("admin_role_tab", role="patients"))

        # 3️⃣ Create and add new blacklist record
        new_entry = Blacklist(patient_id=patient_id)
        db.session.add(new_entry)
        db.session.commit()

        # 4️⃣ Confirmation message for admin
        flash(f"Patient '{patient.full_name}' has been blacklisted.", "warning")

        # 5️⃣ Redirect back to the Patients tab
        return redirect(url_for("admin_role_tab", role="patients"))


# -----------------------------------------------------------------------
# ------------------- Doctor Management Routes --------------------------
# -----------------------------------------------------------------------


# ✅ Add new doctor (simple version)
    @app.route("/admin/doctor/add", methods=["GET", "POST"])
    @admin_required
    def add_doctor():
        """Add a new doctor."""
        if request.method == "POST":
            full_name = request.form["full_name"]
            email = request.form["email"]
            password = request.form["password"]
            experience = request.form["experience"]
            department_id = request.form.get("department_id")

            new_doctor = Doctor(
                full_name=full_name,
                email=email,
                password=password,
                experience=experience,  # default password
                department_id=department_id
            )
            db.session.add(new_doctor)
            db.session.commit()
            flash("Doctor added successfully!", "success")
            return redirect(url_for("admin_role_tab", role="doctors"))

        departments = Department.query.all()
        return render_template("admin/parts/add_doctor.html", departments=departments, mode='add')
    
    # ✅ Edit doctor
    @app.route("/admin/doctor/edit/<int:doctor_id>", methods=["GET", "POST"])
    @admin_required
    def edit_doctor(doctor_id):
        """Edit doctor details."""
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            flash("Doctor not found.", "warning")
            return redirect(url_for("admin_doctors"))

        if request.method == "POST":
            doctor.full_name = request.form["full_name"]
            doctor.email = request.form["email"]
            doctor.phone_no = request.form["phone_no"]
            doctor.department_id = request.form.get("department_id")
            db.session.commit()
            flash("Doctor updated successfully.", "success")
            return redirect(url_for("admin_doctors"))

        departments = Department.query.all()
        return render_template("admin/parts/add_doctor.html", doctor=doctor, departments=departments, mode='edit')
    
    # ✅ Delete doctor
    @app.route("/admin/doctor/delete/<int:doctor_id>", methods=["POST"])
    @admin_required
    def delete_doctor(doctor_id):
        """Delete a doctor."""
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            flash("Doctor not found.", "warning")
        else:
            db.session.delete(doctor)
            db.session.commit()
            flash(f"Doctor '{doctor.full_name}' deleted.", "success")
        return redirect(url_for("admin_role_tab", role="doctors"))
    
    # ✅ Blacklist doctor
    @app.route("/admin/doctor/blacklist/<int:doctor_id>", methods=["POST"])
    @admin_required
    def blacklist_doctor(doctor_id):
        """Add doctor to blacklist."""
        existing = Doctor_blacklist.query.filter_by(doctor_id=doctor_id).first()
        if existing:
            flash("Doctor already blacklisted.", "info")
        else:
            entry = Doctor_blacklist(doctor_id=doctor_id)
            db.session.add(entry)
            db.session.commit()
            flash("Doctor blacklisted.", "warning")
        return redirect(url_for("admin_role_tab", role="doctors"))
    
    # ✅ Unblacklist doctor
    @app.route("/admin/doctor/unblacklist/<int:doctor_id>", methods=["POST"])
    @admin_required
    def unblacklist_doctor(doctor_id):
        """Remove doctor from blacklist."""
        entry = Doctor_blacklist.query.filter_by(doctor_id=doctor_id).first()
        if not entry:
            flash("Doctor is not blacklisted.", "info")
        else:
            db.session.delete(entry)
            db.session.commit()
            flash("Doctor unblacklisted.", "success")
        return redirect(url_for("admin_role_tab", role="doctors"))

