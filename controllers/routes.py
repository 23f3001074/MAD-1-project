from flask import render_template, request, redirect, url_for,flash, session
from database.model import db,Admin, Patient, Doctor, Blacklist
from datetime import datetime


# Home: show patient login by default
def setup_routes(app):
    @app.route("/")
    def index():
        return render_template("login.html", role="patient", tab="login")

    # This route must exist so url_for('role_tab', role=..., tab=...) works.
    # We name the function `role_tab` so the endpoint is 'role_tab'.
    @app.route("/<role>/<tab>")
    def role_tab(role, tab):
        # role is one of: admin / doctor / patient
        # tab is one of: login / register
        return render_template("login.html", role=role, tab=tab)

    @app.route("/login", methods=["POST","GET"])
    def login():
        if request.method == "POST":
            role = request.form.get("role")
            email = request.form.get("email")
            password = request.form.get("password")

            if email and password:
                if role == "admin":
                    this_user = Admin.query.filter_by(username=email).first()
                    if this_user and this_user.password == password:
                        session['user_id'] = this_user.username
                        session['role'] = 'admin'
                        return redirect(url_for("admin_dashboard", role=role))
                    flash("Incorrect admin or password")
                    return redirect(url_for("role_tab", role=role, tab="login"))

                elif role == "doctor":
                    this_user = Doctor.query.filter_by(email=email).first()
                    if this_user and this_user.password == password:
                        session['user_id'] = this_user.username
                        session['role'] = 'doctor'
                        return redirect(url_for("dashboard", role=role))
                    flash("Incorrect doctor or password")
                    return redirect(url_for("role_tab", role=role, tab="login"))

                else:  # patient
                    this_user = Patient.query.filter_by(email=email).first()
                    if this_user and this_user.password == password:
                        session['user_id'] = this_user.username
                        session['role'] = 'patient'
                        return redirect(url_for("dashboard", role=role))
                    flash("Incorrect email or password")
                    return redirect(url_for("role_tab", role=role, tab="login"))

            flash("Please enter email and password")
            return redirect(url_for("role_tab", role=role, tab="login"))

        # GET request
        role = request.args.get("role", "patient")
        return redirect(url_for("role_tab", role=role, tab="login"))

            
    @app.route("/register", methods=["POST"])
    def register():
        if request.method == "POST":
            role = request.form.get("role")
            full_name = request.form.get("full_name")
            email = request.form.get("email")
            password = request.form.get("password")
            phone_no = request.form.get("phone_no")
            dob_str = request.form.get("dob")          # string from form, e.g. "2005-01-01"
            address = request.form.get("address")

            # convert dob_str -> datetime.date (form input type="date" returns YYYY-MM-DD)
            dob = None
            if dob_str:
                try:
                    dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid date format for Date of Birth.")
                    return redirect(url_for("role_tab", role=role, tab="register"))

            if role == "patient":
                existing_user = Patient.query.filter_by(email=email).first()
                balcklist_entry = Blacklist.query.filter_by(patient_id=existing_user.patient_id).first() if existing_user else None
                if existing_user:
                    flash("Email already registered")
                    return redirect(url_for("role_tab", role=role, tab="register"))
                elif balcklist_entry:
                    flash("You are blacklisted and cannot register.")
                    return redirect(url_for("role_tab", role=role, tab="register"))

                new_patient = Patient(
                    full_name=full_name,
                    email=email,
                    password=password,  # consider hashing passwords (see note below)
                    phone_no=phone_no,
                    dob=dob,             # pass a Python date object (or None)
                    address=address
                )
                db.session.add(new_patient)
                db.session.commit()
                flash("Registration successful! Please log in.")
                return redirect(url_for("role_tab", role=role, tab="login"))

            flash("Registration for this role is not implemented yet.")
            return redirect(url_for("role_tab", role=role, tab="register"))

        # GET fallback (won't be used for POST-only route, but kept from your original)
        role = request.args.get("role", "patient")
        return redirect(url_for("role_tab", role=role, tab="login"))
    
    # ✅ ---- Logout route ----
    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()                 # remove all session data
        flash("Logged out successfully")
        return redirect(url_for("login"))
    
    

