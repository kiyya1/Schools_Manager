import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pdfkit

app = Flask(__name__)

# System Configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'kiyya-secret-key-2026')
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///kiyya_students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Models Definition
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    grade = db.Column(db.String(50), nullable=False)
    phone_number = db.Column(db.String(30), nullable=False)
    payment_type = db.Column(db.String(20), default='Monthly')
    bus_service = db.Column(db.String(20), default='Not Needed')
    registration_status = db.Column(db.String(20), default='Pending')
    payment_status = db.Column(db.String(20), default='Unpaid')
    amount_paid = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monthly_fee = db.Column(db.Float, default=3000.0)
    term_fee = db.Column(db.Float, default=8000.0)
    bus_fee = db.Column(db.Float, default=1500.0)
    system_name = db.Column(db.String(100), default='Kiyya Students Manager')

# Routes Definition
@app.route('/')
def index():
    students = Student.query.order_by(Student.id.desc()).all()
    settings = Setting.query.first()
    if not settings:
        settings = Setting()
        db.session.add(settings)
        db.session.commit()
    return render_template('index.html', students=students, settings=settings)

@app.route('/add_student', methods=['POST'])
def add_student():
    full_name = request.form.get('full_name')
    grade = request.form.get('grade')
    phone_number = request.form.get('phone_number')
    payment_type = request.form.get('payment_type', 'Monthly')
    bus_service = request.form.get('bus_service', 'Not Needed')
    amount_paid = float(request.form.get('amount_paid', 0.0) or 0.0)

    new_student = Student(
        full_name=full_name,
        grade=grade,
        phone_number=phone_number,
        payment_type=payment_type,
        bus_service=bus_service,
        amount_paid=amount_paid
    )
    db.session.add(new_student)
    db.session.commit()
    flash('Student added successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/receipt/<int:student_id>')
def receipt(student_id):
    student = Student.query.get_or_404(student_id)
    settings = Setting.query.first()
    
    if not settings:
        settings = Setting()
        db.session.add(settings)
        db.session.commit()

    # ክፍያዎችን እና ቀሪ ሂሳብን ማስላት
    if student.payment_type == 'Term':
        base_fee = float(getattr(settings, 'term_fee', 8000.0) or 8000.0)
    else:
        base_fee = float(getattr(settings, 'monthly_fee', 3000.0) or 3000.0)

    if student.bus_service and student.bus_service != 'Not Needed':
        bus_fee = float(getattr(settings, 'bus_fee', 1500.0) or 1500.0)
    else:
        bus_fee = 0.0

    total_expected = base_fee + bus_fee
    amount_paid = float(student.amount_paid) if student.amount_paid else 0.0
    remaining_balance = max(0.0, total_expected - amount_paid)

    # ሁሉንም አስፈላጊ ቫሪያብሎች ወደ ቴምፕሌት መላክ
    return render_template(
        'receipt.html', 
        student=student, 
        settings=settings,
        base_fee=base_fee,
        bus_fee=bus_fee,
        total_expected=total_expected,
        remaining_balance=remaining_balance,
        is_pdf=False
    )

@app.route('/settings', methods=['GET', 'POST'])
def update_settings():
    settings = Setting.query.first()
    if not settings:
        settings = Setting()
        db.session.add(settings)

    if request.method == 'POST':
        settings.monthly_fee = float(request.form.get('monthly_fee', 3000.0))
        settings.term_fee = float(request.form.get('term_fee', 8000.0))
        settings.bus_fee = float(request.form.get('bus_fee', 1500.0))
        settings.system_name = request.form.get('system_name', 'Kiyya Students Manager')
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('settings.html', settings=settings)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)