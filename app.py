import os
import sys
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'kiyya_secret_key_123'

# Database Configuration (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class FeeSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tuition_fee = db.Column(db.Float, default=3000.0)
    bus_fee = db.Column(db.Float, default=1500.0)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    section = db.Column(db.String(10), default='A')
    phone = db.Column(db.String(20), nullable=True)
    bus_service = db.Column(db.String(50), default='አልፈልግም (No Bus)')
    bus_fee = db.Column(db.Float, default=0.0)
    tuition_fee = db.Column(db.Float, default=0.0)
    total_expected = db.Column(db.Float, default=0.0)
    amount_paid = db.Column(db.Float, default=0.0)
    balance_due = db.Column(db.Float, default=0.0)
    address = db.Column(db.String(200), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    ft_approval_no = db.Column(db.String(100), nullable=True)
    payment_type = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='Pending')
    date_registered = db.Column(db.String(50), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

with app.app_context():
    db.create_all()
    # Default Admin (admin / admin123)
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password_hash=generate_password_hash('admin123')))
    # Default Fees
    if not db.session.get(FeeSetting, 1):
        db.session.add(FeeSetting(id=1, tuition_fee=3000.0, bus_fee=1500.0))
    db.session.commit()

# --- Helper Function ---
def get_fees():
    setting = db.session.get(FeeSetting, 1)
    if setting:
        return setting.tuition_fee, setting.bus_fee
    return 3000.0, 1500.0

# --- Public Routes ---
@app.route('/')
def register_page():
    tuition, bus = get_fees()
    return render_template('register.html', bus_fee=bus, tuition_fee=tuition)

@app.route('/add_student', methods=['POST'])
def add_student():
    tuition, bus = get_fees()
    
    full_name = request.form.get('full_name')
    grade = request.form.get('grade')
    phone = request.form.get('phone')
    bus_choice = request.form.get('bus_service', 'አልፈልግም (No Bus)')
    address = request.form.get('address')
    payment_method = request.form.get('payment_method')
    ft_approval_no = request.form.get('ft_approval_no')
    payment_type = request.form.get('payment_type')
    amount_paid = float(request.form.get('amount_paid', 0))
    
    # ራስ-ሰር የባስ ክፍያ እና ጠቅላላ ሂሳብ ስሌት
    actual_bus_fee = bus if bus_choice == 'እፈልጋለሁ (Yes Bus)' else 0.0
    total_expected = tuition + actual_bus_fee
    balance_due = total_expected - amount_paid
    
    existing_count = Student.query.filter_by(grade=grade).count()
    section_index = existing_count // 30
    assigned_section = string.ascii_uppercase[section_index % 26] 

    new_student = Student(
        full_name=full_name, grade=grade, section=assigned_section,
        phone=phone, bus_service=bus_choice, bus_fee=actual_bus_fee,
        tuition_fee=tuition, total_expected=total_expected,
        amount_paid=amount_paid, balance_due=balance_due,
        address=address, payment_method=payment_method,
        ft_approval_no=ft_approval_no, payment_type=payment_type,
        status='Pending'
    )
    db.session.add(new_student)
    db.session.commit()
    
    flash(f'የተማሪ {full_name} ምዝገባ ተጠናቋል! ጠቅላላ የሚፈለግበት፦ {total_expected} ETB', 'success')
    return redirect(url_for('register_page'))

# --- Auth Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('admin_dashboard'))
        flash('የተሳሳተ Username ወይም Password!', 'danger')
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    tuition, bus = get_fees()
    students = Student.query.order_by(Student.id.desc()).all()
    return render_template('admin.html', students=students, tuition_fee=tuition, bus_fee=bus)

@app.route('/update_fees', methods=['POST'])
def update_fees():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    setting = db.session.get(FeeSetting, 1)
    if setting:
        setting.tuition_fee = float(request.form.get('tuition_fee', 3000))
        setting.bus_fee = float(request.form.get('bus_fee', 1500))
        db.session.commit()
        flash('የክፍያ ዋጋዎች በስኬት ተሻሽለዋል!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/receipt/<int:id>')
def print_receipt(id):
    student = db.session.get(Student, id)
    if not student:
        flash('ተማሪው አልተገኘም!', 'danger')
        return redirect(url_for('admin_dashboard'))
    return render_template('receipt.html', student=student)

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    old_pw = request.form.get('old_password')
    new_pw = request.form.get('new_password')
    
    if user and check_password_hash(user.password_hash, old_pw):
        user.password_hash = generate_password_hash(new_pw)
        db.session.commit()
        flash('የይለፍ ቃልህ በስኬት ተቀይሯል!', 'success')
    else:
        flash('የድሮው የይለፍ ቃል የተሳሳተ ነው!', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_student/<int:id>')
def delete_student(id):
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    student = db.session.get(Student, id)
    if student:
        db.session.delete(student)
        db.session.commit()
        flash(f'የተማሪ {student.full_name} መረጃ ተሰርዟል!', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('ወጥተዋል!', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)