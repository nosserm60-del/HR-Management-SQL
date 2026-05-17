from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
import pyodbc
import os
import json
import base64
from datetime import datetime, date
import traceback
import face_recognition
import numpy as np

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'mahmoud_123_safe'

UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=.\\SQLEXPRESS01;'
        'DATABASE=hr_system;'
        'Trusted_Connection=yes;'
    )
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"خطأ في الاتصال: {e}")
        return None

# ============================================================
# دالة مساعدة: استخراج Face Encoding من مسار صورة
# ============================================================
def extract_face_encoding(image_path):
    """
    تأخذ مسار الصورة وترجع الـ encoding كـ JSON string.
    لو مفيش وجه في الصورة بترجع None.
    """
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        if encodings:
            # نحوّل الـ numpy array لـ list عشان نقدر نحفظه كـ JSON
            return json.dumps(encodings[0].tolist())
        else:
            print("⚠️ لم يتم اكتشاف وجه في الصورة")
            return None
    except Exception as e:
        print(f"❌ خطأ في استخراج Face Encoding: {e}")
        return None

# ============================================================
# LOGIN
# ============================================================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == '123':
            session.update({'logged_in': True, 'user_id': 1, 'user_name': 'Admin', 'role': 'Admin'})
            return redirect(url_for('dashboard'))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session.update({'logged_in': True, 'user_id': user.id, 'user_name': user.name, 'role': user.role})
            return redirect(url_for('dashboard') if user.role == 'Admin' else url_for('employee_dashboard'))
        return "❌ بيانات غير صحيحة"
    return render_template('login.html')

# ============================================================
# DASHBOARD
# ============================================================
@app.route('/dashboard')
def dashboard():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM employees")
    total = cursor.fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date=?", (today,))
    present = cursor.fetchone()[0]
    absent = total - present
    conn.close()
    return render_template('dashboard.html', total=total, present=present, absent=absent, today=today)

@app.route('/emp_dashboard')
def employee_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('employee_dashboard.html', name=session['user_name'])

# ============================================================
# EMPLOYEES
# ============================================================
@app.route('/employees')
def employees():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees")
    all_emp = cursor.fetchall()
    conn.close()
    return render_template('employees.html', employees=all_emp)

# ============================================================
# ADD EMPLOYEE - مع Face Encoding
# ============================================================
@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name        = request.form.get('name')
        username    = request.form.get('username')
        password    = request.form.get('password')
        dept        = request.form.get('dept')
        role        = request.form.get('role')
        hourly_rate = request.form.get('hourly_rate') or 0
        photo       = request.files.get('photo')

        filename      = ""
        face_encoding = None   # القيمة الافتراضية

        # ── حفظ الصورة ──────────────────────────────────────
        if photo and photo.filename != "":
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{photo.filename}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(filepath)

            # ── استخراج Face Encoding بعد الحفظ ─────────────
            face_encoding = extract_face_encoding(filepath)

            if face_encoding is None:
                # نُبلّغ الأدمن إن الصورة مش فيها وجه واضح
                flash("⚠️ تحذير: لم يتم اكتشاف وجه واضح في الصورة. سيتم حفظ الموظف بدون بصمة وجه.", "warning")

        # ── حفظ في قاعدة البيانات ────────────────────────────
        conn   = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO employees
                    (name, username, password, department, role, photo, hourly_rate, face_encoding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, username, password, dept, role, filename, hourly_rate, face_encoding))
            conn.commit()
            flash("✅ تم إضافة الموظف بنجاح", "success")
        except Exception as e:
            print(f"خطأ: {e}")
            return f"❌ حدث خطأ: {str(e)}"
        finally:
            conn.close()

        return redirect(url_for('employees'))

    return render_template('add_employee.html')

# ============================================================
# DELETE EMPLOYEE
# ============================================================
@app.route('/delete_employee/<int:id>', methods=['GET', 'POST'])
@app.route('/admin/delete_employee/<int:id>', methods=['GET', 'POST'])
def delete_employee(id):
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM employees WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('employees'))

# ============================================================
# ATTENDANCE - CHECK IN / CHECK OUT
# ============================================================
@app.route('/check_in', methods=['POST'])
def check_in():
    if not session.get('logged_in'):
        return jsonify({"message": "سجل دخولك أولاً"}), 401
    user_id      = session.get('user_id')
    now          = datetime.now()
    today        = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM attendance WHERE user_id=? AND date=?", (user_id, today))
        if cursor.fetchone():
            return jsonify({"message": "❌ سجلت حضور بالفعل اليوم"})
        cursor.execute('''
            INSERT INTO attendance (user_id, date, time, status)
            VALUES (?, ?, ?, ?)
        ''', (user_id, today, current_time, "حاضر"))
        conn.commit()
        return jsonify({"message": "✅ تم تسجيل الحضور"})
    except Exception as e:
        return jsonify({"message": f"❌ خطأ: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/check_out', methods=['POST'])
def check_out():
    if not session.get('logged_in'):
        return jsonify({"message": "سجل دخولك أولاً"}), 401
    user_id = session.get('user_id')
    now     = datetime.now()
    today   = now.strftime("%Y-%m-%d")
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM attendance WHERE user_id=? AND date=? AND check_out_time IS NULL",
            (user_id, today)
        )
        record = cursor.fetchone()
        if record:
            cursor.execute(
                "UPDATE attendance SET check_out_time=? WHERE user_id=? AND date=?",
                (now.strftime("%H:%M:%S"), user_id, today)
            )
            conn.commit()
            return jsonify({"message": "✅ تم الانصراف"})
        return jsonify({"message": "⚠️ لا يوجد سجل حضور مفتوح"})
    except Exception as e:
        return jsonify({"message": f"❌ خطأ: {str(e)}"}), 500
    finally:
        conn.close()

# ============================================================
# ATTENDANCE LOGS
# ============================================================
@app.route('/attendance')
@app.route('/admin_attendance')
def attendance_logs():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT attendance.*, employees.name
        FROM attendance
        JOIN employees ON attendance.user_id = employees.id
        ORDER BY attendance.date DESC
    ''')
    logs = cursor.fetchall()
    conn.close()
    return render_template('admin_attendance.html', logs=logs)

# ============================================================
# SET ZONE
# ============================================================
@app.route('/set_zone', methods=['GET', 'POST'])
def set_zone():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn   = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        lat    = request.form.get('lat')
        lng    = request.form.get('lng')
        radius = request.form.get('radius')
        try:
            cursor.execute(
                "UPDATE settings SET office_lat=?, office_lng=?, allowed_radius=? WHERE id=1",
                (float(lat), float(lng), int(radius))
            )
            conn.commit()
            flash("✅ تم حفظ النطاق", "success")
        except Exception as e:
            flash(f"❌ خطأ: {str(e)}", "danger")
        finally:
            conn.close()
        return redirect(url_for('set_zone'))
    cursor.execute("SELECT * FROM settings WHERE id=1")
    zone = cursor.fetchone()
    conn.close()
    return render_template('set_zone.html', zone=zone)

# ============================================================
# LEAVE REQUESTS
# ============================================================
@app.route('/request_leave', methods=['GET', 'POST'])
def request_leave():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        user_id = session.get('user_id')
        l_type  = request.form.get('leave_type')
        s_date  = request.form.get('start_date')
        e_date  = request.form.get('end_date')
        reason  = request.form.get('reason')
        conn   = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, reason, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, l_type, s_date, e_date, reason, 'Pending'))
            conn.commit()
        except Exception as e:
            return f"❌ خطأ: {str(e)}"
        finally:
            conn.close()
        return redirect(url_for('employee_dashboard'))
    return render_template('request_leave.html')

@app.route('/admin/leaves')
def admin_leaves():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT lr.*, e.name
        FROM leave_requests lr
        JOIN employees e ON lr.user_id = e.id
        ORDER BY lr.id DESC
    ''')
    requests = cursor.fetchall()
    conn.close()
    return render_template('admin_leaves.html', requests=requests)

@app.route('/admin/update_leave/<int:req_id>', methods=['POST'])
def update_leave_status(req_id):
    if session.get('role') != 'Admin':
        abort(403)
    new_status = request.form.get('status')
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leave_requests SET status=? WHERE id=?", (new_status, req_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_leaves'))

# ============================================================
# PAYROLL
# ============================================================
@app.route('/admin/payroll')
@app.route('/payroll')
def admin_payroll():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, hourly_rate FROM employees WHERE role='Employee'")
    employees = cursor.fetchall()
    salaries = []
    for emp in employees:
        salaries.append({
            'id': emp.id,
            'name': emp.name,
            'hourly_rate': emp.hourly_rate,
            'total_hours': 0,
            'approved_leaves': 0,
            'expected_salary': 0
        })
    conn.close()
    return render_template('payroll.html', salaries=salaries)

@app.route('/admin/save_salary', methods=['POST'])
def save_salary():
    if session.get('role') != 'Admin':
        return jsonify({"status": "error", "message": "غير مصرح"}), 403
    data      = request.get_json(silent=True) or request.form
    emp_id    = data.get('emp_id')
    total_hours = data.get('total_hours')
    hourly_rate = data.get('hourly_rate')
    basic     = data.get('basic')
    bonus     = data.get('bonus')
    deduction = data.get('deduction')
    net       = data.get('net')
    month     = datetime.now().strftime('%Y-%m')
    conn   = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO payroll_history
                (user_id, month, total_hours, hourly_rate, basic_salary, bonus, deductions, net_salary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, month, total_hours, hourly_rate, basic, bonus, deduction, net))
        conn.commit()
        return jsonify({"status": "success", "message": "✅ تم إصدار الراتب"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"❌ خطأ: {str(e)}"})
    finally:
        conn.close()

@app.route('/my_payslips')
def my_payslips():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payroll_history WHERE user_id=? ORDER BY id DESC", (user_id,))
    payslips = cursor.fetchall()
    conn.close()
    return render_template('my_payslips.html', payslips=payslips)

# ============================================================
# ANNOUNCEMENTS
# ============================================================
@app.route('/add_announcement', methods=['GET', 'POST'])
@app.route('/admin_announcements', methods=['GET', 'POST'])
def add_announcement():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    conn   = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        title   = request.form.get('title')
        message = request.form.get('message')
        cursor.execute(
            "INSERT INTO announcements (title, content, created_at) VALUES (?, ?, ?)",
            (title, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        return redirect(url_for('add_announcement'))
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    all_news = cursor.fetchall()
    conn.close()
    return render_template('admin_announcements.html', announcements=all_news, news=all_news)

@app.route('/company_feed', methods=['GET', 'POST'])
def company_feed():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn   = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    news = cursor.fetchall()
    conn.close()
    return render_template('company_feed.html', news=news, comments=[])

# ============================================================
# LOGOUT
# ============================================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)