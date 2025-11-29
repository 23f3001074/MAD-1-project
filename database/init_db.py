from database.model import db, Admin, Department
from sqlalchemy import text

def init_db(app):

  # create database tables if not already
  with app.app_context():
    db.create_all()


    # Create an admin user if it doesn't exist
    admin = Admin.query.filter_by(username='admin@gmail.com').first()
    if not admin:
        admin = Admin(username='admin@gmail.com', password='admin123')
        db.session.add(admin)
        db.session.commit()

    # Predefined departments
    default_departments = ['Cardiology', 'Neurology', 'Orthopedics', 'Pediatrics', 'Dermatology']

    for dept_name in default_departments:
        # Check if the department already exists
        existing_dept = Department.query.filter_by(department_name=dept_name).first()
        if not existing_dept:
            new_dept = Department(department_name=dept_name, description=f'Description for {dept_name} department.And more details about services offered.')
            db.session.add(new_dept)

    # Commit once after all inserts

    

    db.session.commit()


