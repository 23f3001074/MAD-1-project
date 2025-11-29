from database import db
import datetime


class Admin(db.Model):
  username = db.Column(db.String(30), primary_key=True)
  password = db.Column(db.String(256), nullable=False)


class Patient(db.Model):
  patient_id = db.Column(db.Integer, primary_key=True)
  full_name = db.Column(db.String(64), nullable = False)
  email = db.Column(db.String(254), nullable=False, unique=True)
  password = db.Column(db.String(256), nullable=False)
  phone_no = db.Column(db.String(15), nullable = False, unique=True)
  dob = db.Column(db.Date, nullable=False)
  address = db.Column(db.Text, nullable=False)

  # relationship
  appointments = db.relationship('Appointment', backref='patient', lazy=True)

class Doctor(db.Model):
  doctor_id = db.Column(db.Integer, primary_key=True) 
  full_name = db.Column(db.String(64), nullable = False)
  email = db.Column(db.String(254), nullable=False, unique=True)
  password = db.Column(db.String(256), nullable=False)
  department_id = db.Column(db.Integer, db.ForeignKey('department.department_id'))  # dropdown values
  experience  = db.Column(db.Integer)      # years of experience (whole years)

  #relationship
  appointments = db.relationship('Appointment', backref='doctor', lazy=True)

class Appointment(db.Model):
  appointment_id = db.Column(db.Integer, primary_key=True)
  patient_id = db.Column(db.Integer, db.ForeignKey('patient.patient_id'), nullable=False)
  doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.doctor_id'), nullable=False)
  date = db.Column(db.Date, nullable=False)
  time = db.Column(db.Time, nullable=False)
  department = db.Column(db.String(40),db.ForeignKey('department.department_name'), nullable=False)
  status = db.Column(db.String(30), nullable=False) # dropdown like booked, complete, cancelled

  # relationship
  treatment = db.relationship('Treatment', backref='appointment', uselist=False)

class Treatment(db.Model):
  treatment_id = db.Column(db.Integer, primary_key=True)
  appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.appointment_id'), nullable=False, unique=True)
  diagnosis = db.Column(db.String(255), nullable=False)
  prescription = db.Column(db.Text, nullable=True)
  note = db.Column(db.Text, nullable=True)


class Department(db.Model):
  department_id = db.Column(db.Integer, primary_key=True)
  department_name = db.Column(db.String(40), nullable=False, unique=True)
  description = db.Column(db.Text, nullable=True)

  # relationship
  doctors = db.relationship('Doctor', backref='department', lazy=True)

class Blacklist(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  patient_id = db.Column(db.Integer, db.ForeignKey('patient.patient_id'), nullable=False)

class Doctor_blacklist(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.doctor_id'), nullable=False)


class DoctorAvailability(db.Model):
    """
    Minimal DoctorAvailability model.
    - Keeps columns for compatibility.
    - Shifts are fixed: SHIFT1 = 09:00-12:00, SHIFT2 = 13:00-16:00.
    """
    __tablename__ = "doctor_availability"

    availability_id = db.Column(db.Integer, primary_key=True)
    doctor_id     = db.Column(db.Integer, db.ForeignKey("doctor.doctor_id"), nullable=False)
    date          = db.Column(db.Date, nullable=False, index=True)

    # Flags telling whether shift is enabled for that date
    shift1_enabled = db.Column(db.Boolean, default=False, nullable=False)
    shift1_start   = db.Column(db.Time, nullable=True)
    shift1_end     = db.Column(db.Time, nullable=True)

    shift2_enabled = db.Column(db.Boolean, default=False, nullable=False)
    shift2_start   = db.Column(db.Time, nullable=True)
    shift2_end     = db.Column(db.Time, nullable=True)

    __table_args__ = (db.UniqueConstraint('doctor_id', 'date', name='uq_doc_date'),)

    # Fixed shift times (use these in routes; doctors cannot change them)
    SHIFT1_START = datetime.time(9, 0)   # 09:00
    SHIFT1_END   = datetime.time(12, 0)  # 12:00
    SHIFT2_START = datetime.time(13, 0)  # 13:00
    SHIFT2_END   = datetime.time(16, 0)  # 16:00

    def __repr__(self):
        return f"<DoctorAvailability doctor={self.doctor_id} date={self.date} s1={self.shift1_enabled} s2={self.shift2_enabled}>"




