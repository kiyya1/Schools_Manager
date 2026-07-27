import os
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from xhtml2pdf import pisa

app = Flask(__name__)
app.secret_key = 'super-secret-key-change-this'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(10), nullable=False, default='A')
    phone = db.Column(db.String(20), nullable=False)
    bus_service = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    payment_type = db.Column(db.String(50), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    ft_approval_no = db.Column(db.String(100), nullable=True)
    amount_paid = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monthly_fee = db.Column(db.Float, default=3000.0)
    term_fee = db.Column(db.Float, default=8000.0)
    bus_fee = db.Column(db.Float, default=1500.0)
    class_capacity = db.Column(db.Integer, default=30)
    default_address = db.Column(db.String(200), default="አቃቂ ቃሊቲ ወረዳ 09")

class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

with app.app_context():
    db.create_all()
    if not AdminUser.query.filter_by(username='admin').first():
        db.session.add(AdminUser(username='admin', password='adminpassword'))
    if not Setting.query.first():
        db.session.add(Setting())
    db.session.commit()

def get_next_section(grade, capacity):
    existing_count = Student.query.filter_by(grade=grade).count()
    section_index = existing_count // capacity
    return chr(65 + section_index)

@app.route('/')
@app.route('/register')
def register():
    settings = Setting.query.first()
    return render_template('register.html', settings=settings)

@app.route('/add_student', methods=['POST'])
def add_student():
    settings = Setting.query.first()
    capacity = settings.class_capacity if settings else 30

    grade = request.form.get('grade')
    assigned_section = get_next_section(grade, capacity)

    new_student = Student(
        full_name=request.form.get('full_name'),
        grade=grade,
        section=assigned_section,
        phone=request.form.get('phone'),
        bus_service=request.form.get('bus_service'),
        address=request.form.get('address'),
        payment_type=request.form.get('payment_type'),
        payment_method=request.form.get('payment_method'),
        ft_approval_no=request.form.get('ft_approval_no'),
        amount_paid=float(request.form.get('amount_paid', 0))
    )
    db.session.add(new_student)
    db.session.commit()

    flash('ተማሪው በስኬት ተመዝግቧል!', 'success')
    return redirect(url_for('view_receipt', student_id=new_student.id))

@app.route('/receipt/<int:student_id>')
def view_receipt(student_id):
    student = Student.query.get_or_404(student_id)
    settings = Setting.query.first()
    
    base_fee = (settings.term_fee if settings else 8000.0) if student.payment_type == 'Term Fee' else (settings.monthly_fee if settings else 3000.0)
    bus_fee = (settings.bus_fee if settings else 1500.0) if (student.bus_service and ('Bus Needed' in student.bus_service or 'እፈልጋለሁ' in student.bus_service)) else 0.0
    total_expected = base_fee + bus_fee
    remaining_balance = max(0.0, total_expected - student.amount_paid)

    return render_template('receipt.html', student=student, settings=settings, base_fee=base_fee, bus_fee=bus_fee, total_expected=total_expected, remaining_balance=remaining_balance)

@app.route('/download_receipt_pdf/<int:student_id>')
def download_receipt_pdf(student_id):
    student = Student.query.get_or_404(student_id)
    settings = Setting.query.first()
    
    base_fee = (settings.term_fee if settings else 8000.0) if student.payment_type == 'Term Fee' else (settings.monthly_fee if settings else 3000.0)
    bus_fee = (settings.bus_fee if settings else 1500.0) if (student.bus_service and ('Bus Needed' in student.bus_service or 'እፈልጋለሁ' in student.bus_service)) else 0.0
    total_expected = base_fee + bus_fee
    remaining_balance = max(0.0, total_expected - student.amount_paid)

    rendered_html = render_template('receipt.html', student=student, settings=settings, base_fee=base_fee, bus_fee=bus_fee, total_expected=total_expected, remaining_balance=remaining_balance, is_pdf=True)
    
    pdf_out = BytesIO()
    pisa_status = pisa.CreatePDF(BytesIO(rendered_html.encode('utf-8')), dest=pdf_out)
    
    if pisa_status.err:
        return "PDF መፍጠር አልተቻለም", 500

    response = make_response(pdf_out.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Receipt_{student.id}.pdf'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = AdminUser.query.filter_by(username=request.form.get('username'), password=request.form.get('password')).first()
        if user:
            session['logged_in'] = True
            return redirect('/admin')
        flash('የተሳሳተ የተጠቃሚ ስም ወይም የይለፍ ቃል!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect('/login')

    settings = Setting.query.first()
    if not settings:
        settings = Setting()
        db.session.add(settings)
        db.session.commit()

    students = Student.query.order_by(Student.id.desc()).all()
    total_students = len(students)
    total_paid = sum(s.amount_paid for s in students if s.amount_paid)
    
    student_data = []
    total_expected = 0.0

    for s in students:
        base_fee = settings.term_fee if s.payment_type == 'Term Fee' else settings.monthly_fee
        bus_addon = settings.bus_fee if (s.bus_service and ('Bus Needed' in s.bus_service or 'እፈልጋለሁ' in s.bus_service)) else 0.0
        expected = base_fee + bus_addon
        remaining = max(0.0, expected - s.amount_paid)

        total_expected += expected
        student_data.append({'student': s, 'expected': expected, 'paid': s.amount_paid, 'remaining': remaining})

    total_unpaid = max(0.0, total_expected - total_paid)

    return render_template('admin.html', student_data=student_data, total_students=total_students, total_expected=total_expected, total_paid=total_paid, total_unpaid=total_unpaid, settings=settings)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not session.get('logged_in'):
        return redirect('/login')
    settings = Setting.query.first()
    if not settings:
        settings = Setting()
        db.session.add(settings)

    settings.monthly_fee = float(request.form.get('monthly_fee', 3000))
    settings.term_fee = float(request.form.get('term_fee', 8000))
    settings.bus_fee = float(request.form.get('bus_fee', 1500))
    settings.class_capacity = int(request.form.get('class_capacity', 30))
    db.session.commit()
    flash('ቅንብሮች በስኬት ተቀይረዋል!', 'success')
    return redirect('/admin')

@app.route('/approve_student/<int:id>')
def approve_student(id):
    if not session.get('logged_in'): return redirect('/login')
    s = Student.query.get_or_404(id)
    s.status = 'Approved'
    db.session.commit()
    return redirect('/admin')

@app.route('/reject_student/<int:id>')
def reject_student(id):
    if not session.get('logged_in'): return redirect('/login')
    s = Student.query.get_or_404(id)
    s.status = 'Rejected'
    db.session.commit()
    return redirect('/admin')

@app.route('/delete_student/<int:id>')
def delete_student(id):
    if not session.get('logged_in'): return redirect('/login')
    s = Student.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)