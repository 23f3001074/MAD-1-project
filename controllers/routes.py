from flask import render_template, request, redirect, url_for




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

    @app.route("/login", methods=["POST"])
    def login():
        role = request.form.get("role", "patient")
        # just print for demo; implement real auth in your real app
        print("Login:", role, request.form.get("email"))
        return redirect(url_for("role_tab", role=role, tab="login"))

    @app.route("/register", methods=["POST"])
    def register():
        role = request.form.get("role", "patient")
        print("Register:", role, request.form.get("email"))
        return redirect(url_for("role_tab", role=role, tab="login"))
