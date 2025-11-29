from flask import Flask, render_template, request, redirect, url_for
from database import db
from database.init_db import init_db

app = Flask(__name__)

# Load config_app function from config and initialize
from config import config_app
config_app(app)

# Initialize the database
db.init_app(app)

# Create tables and default admin
init_db(app)

from controllers.routes import setup_routes
setup_routes(app)

from controllers.admin import setup_admin_routes
setup_admin_routes(app)

from controllers.doctors import setup_doctor_routes
setup_doctor_routes(app)

from controllers.patient import setup_patient_routes
setup_patient_routes(app)

if __name__ == '__main__':
  app.run(debug=True)

