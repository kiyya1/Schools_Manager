import os
import io
import logging
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from xhtml2pdf import pisa

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_wabi_key")

# Logging Configuration
logging.basicConfig(level=logging.INFO)

# Image Upload Configuration
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'students.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + db_path)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(50), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    payment_type = db.Column(db.String(50), nullable=False)
    bus_service = db.Column(db.String(50), default="Not Needed")
    payment_method = db.Column(db.String(50), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    ft_approval_no = db.Column(db.String(100), nullable=True)
    receipt_image = db.Column(db.String(200), nullable=True)
    registration_date = db.Column(db.String(50), nullable=True)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monthly_fee = db.Column(db.Float, default=3000.0)
    term_fee = db.Column(db.Float, default=8000.0)
    bus_fee = db.Column(db.Float, default=1500.0)
    class_capacity = db.Column(db.Integer, default=30)
    default_address = db.Column(db.String(200), default="አቃቂ ቃሊቲ ወረዳ 09")
    telebirr_no = db.Column(db.String(50), default="0911223344")
    cbe_account_no = db.Column(db.String(50), default="1000123456789 (CBE - Wabi School)")
    other_bank_info = db.Column(db.String(100), default="BOA: 45678901 / Awash: 987654321")

# Auto Database Migration for SQLite
def auto_migrate():
    try:
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(student)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if columns:
                if 'receipt_image' not in columns:
                    cursor.execute("ALTER TABLE student ADD COLUMN receipt_image VARCHAR(200)")
                if 'registration_date' not in columns:
                    cursor.execute("ALTER TABLE student ADD COLUMN registration_date VARCHAR(50)")
                if 'section' not in columns:
                    cursor.execute("ALTER TABLE student ADD COLUMN section VARCHAR(50)")
                conn.commit()
            conn.close()
    except Exception as e:
        app.logger.error(f"Migration error: {e}")

with app.app_context():
    db.create_all()
    auto_migrate()
    if not Setting.query.first():
        db.session.add(Setting())
        db.session.commit()

# --- Routes ---

@app.route('/')
def home():
    settings = Setting.query.first()
    return render_template('register.html', settings=settings)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/add_student', methods=['POST'])
def add_student():
    full_name = request.form.get('full_name')
    grade = request.form.get('grade')
    section = request.form.get('section', '')
    phone = request.form.get('phone')
    address = request.form.get('address')
    payment_type = request.form.get('payment_type')
    bus_service = request.form.get('bus_service', 'Not Needed')
    payment_method = request.form.get('payment_method')
    
    try:
        amount_paid = float(request.form.get('amount_paid', 0))
    except (ValueError, TypeError):
        amount_paid = 0.0

    ft_approval_no = request.form.get('ft_approval_no')
    today_str = datetime.now().strftime("%Y-%m-%d")

    file = request.files.get('receipt_image')
    filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    new_student = Student(
        full_name=full_name,
        grade=grade,
        section=section,
        phone=phone,
        address=address,
        payment_type=payment_type,
        bus_service=bus_service,
        payment_method=payment_method,
        amount_paid=amount_paid,
        ft_approval_no=ft_approval_no,
        receipt_image=filename,
        registration_date=today_str
    )
    db.session.add(new_student)
    db.session.commit()

    return redirect(url_for('receipt', student_id=new_student.id))

@app.route('/receipt/<int:student_id>')
def receipt(student_id):
    student = Student.query.get_or_404(student_id)
    settings = Setting.query.first()
    if not settings:
        settings = Setting()

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

@app.route('/download_receipt_pdf/<int:student_id>')
def download_receipt_pdf(student_id):
    student = Student.query.get_or_404(student_id)
    settings = Setting.query.first()
    if not settings:
        settings = Setting()

    base_fee = float(settings.term_fee if student.payment_type == 'Term' else settings.monthly_fee)
    bus_fee = float(settings.bus_fee if (student.bus_service and student.bus_service != 'Not Needed') else 0.0)
    total_expected = base_fee + bus_fee
    amount_paid = float(student.amount_paid) if student.amount_paid else 0.0
    remaining_balance = max(0.0, total_expected - amount_paid)

    rendered_html = render_template(
        'receipt.html', 
        student=student, 
        settings=settings,
        base_fee=base_fee,
        bus_fee=bus_fee,
        total_expected=total_expected,
        remaining_balance=remaining_balance,
        is_pdf=True
    )
    
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(rendered_html), dest=pdf_buffer)
    
    if pisa_status.err:
        return "PDF መፍጠር አልተቻለም"
    
    pdf_buffer.seek(0)
    filename = f"Receipt_{student.full_name.replace(' ', '_')}.pdf"
    return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin123':
            session['logged_in'] = True
            return redirect('/admin')
        else:
            flash('ትክክለኛ ያልሆነ ስም ወይም ፓስወርድ!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect('/login')
    students = Student.query.order_by(Student.id.desc()).all()
    settings = Setting.query.first()
    return render_template('admin.html', students=students, settings=settings)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not session.get('logged_in'):
        return redirect('/login')
    settings = Setting.query.first()
    if not settings:
        settings = Setting()
        db.session.add(settings)

    try:
        settings.monthly_fee = float(request.form.get('monthly_fee', 3000))
        settings.term_fee = float(request.form.get('term_fee', 8000))
        settings.bus_fee = float(request.form.get('bus_fee', 1500))
        settings.class_capacity = int(request.form.get('class_capacity', 30))
    except (ValueError, TypeError):
        pass

    settings.telebirr_no = request.form.get('telebirr_no', '0911223344')
    settings.cbe_account_no = request.form.get('cbe_account_no', '1000123456789')
    settings.other_bank_info = request.form.get('other_bank_info', '')

    db.session.commit()
    flash('ቅንብሮች በስኬት ተቀይረዋል!', 'success')
    return redirect('/admin')

@app.route('/delete_student/<int:id>')
def delete_student(id):
    if not session.get('logged_in'):
        return redirect('/login')
    student = Student.query.get_or_404(id)
    if student.receipt_image:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], student.receipt_image)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    db.session.delete(student)
    db.session.commit()
    flash('ተማሪው በስኬት ተሰርዟል!', 'info')
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)