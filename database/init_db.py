from database.model import db, Admin

def init_db(app):

  # create database tables if not already
  with app.app_context():
    db.create_all()


    # Create an admin user if it doesn't exist
    admin = Admin.query.first()
    if not admin:
      admin = Admin(username='Admin', password='admin123')
      db.session.add(admin)
      db.session.commit()