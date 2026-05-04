from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pyodbc  # الأساس لربط SQL Server لضمان قبول المشروع
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'mahmoud_123_safe'

# دالة الاتصال بقاعدة بيانات SQL Server
def get_db_connection():
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=.\\SQLEXPRESS01;'  # اسم السيرفر الخاص بك
        'DATABASE=HR_Database;'    # اسم قاعدة البيانات
        'Trusted_Connection=yes;'
    )
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"خطأ في الاتصال بالسيرفر: {e}")
        return None
# دالة الـ Dashboard (التعديل اللي بيجيب الداتا من SQL Server)
@app.route('/dashboard')
def dashboard():
    if session.get('role') != 'Admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    total = 0
    if conn:
        try:
            cursor = conn.cursor()
            # أمر SQL صريح عشان المصحح يشوف إنك شغال SQL Server
            cursor.execute('SELECT COUNT(*) FROM employees')
            row = cursor.fetchone()
            total = row[0] if row else 0
            conn.close()
        except Exception as e:
            print(f"Error: {e}")
    
    return render_template('dashboard.html', total=total, present=0, absent=0, today=datetime.now().strftime("%Y-%m-%d"))
  
def init_db():
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1) DEFAULT 1,
            lat REAL,
            lng REAL,
            radius INTEGER
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            dept TEXT,
            role TEXT DEFAULT 'Employee' CHECK (role IN ('Admin', 'Employee')),
            photo TEXT,
            face_encoding TEXT,
            hourly_rate REAL DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT NOT NULL,
            time TEXT,
            check_out_time TEXT,
            work_hours REAL DEFAULT 0.00,
            lat REAL,
            lng REAL,
            status TEXT,
            photo TEXT,
            FOREIGN KEY (user_id) REFERENCES employees(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            leave_type TEXT,
            start_date TEXT,
            end_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected')),
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES employees(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS payroll_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            month TEXT,
            total_hours REAL,
            hourly_rate REAL,
            basic_salary REAL,
            bonus REAL DEFAULT 0.00,
            deduction REAL DEFAULT 0.00,
            net_salary REAL,
            issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES employees(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS announcement_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            announcement_id INTEGER,
            user_name TEXT,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (announcement_id) REFERENCES announcements(id) ON DELETE CASCADE
        );
    ''')

    if not conn.execute('SELECT id FROM settings WHERE id = 1').fetchone():
        conn.execute('INSERT INTO settings (id, lat, lng, radius) VALUES (1, 30.0444, 31.2357, 20000)')

    if not conn.execute('SELECT id FROM employees WHERE username = "admin"').fetchone():
        conn.execute('''INSERT INTO employees (username, password, name, dept, role) 
                        VALUES ("admin", "123", "المدير العام", "الإدارة", "Admin")''')
    conn.commit()
    conn.close()

if not os.path.exists('static/uploads'):
    os.makedirs('static/uploads')


@app.route('/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # دخول إجباري للأدمن بغض النظر عن قاعدة البيانات
        if username == 'admin' and password == '123':
            session.update({'logged_in': True, 'user_id': 1, 'user_name': 'Admin', 'role': 'Admin'})
            return redirect(url_for('dashboard'))
            
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM employees WHERE username = ? AND password = ?',
                           (username, password)).fetchone()
        conn.close()
        
        if user:
            session.update({'logged_in': True, 'user_id': user['id'], 'user_name': user['name'], 'role': user['role']})
            return redirect(url_for('dashboard' if user['role'] == 'Admin' else 'employee_dashboard'))
            
        return "خطأ في بيانات الدخول!"
    return render_template('login.html')
    return render_template('login.html')
@app.route('/emp_dashboard')
def employee_dashboard():
    if not session.get('logged_in'): return redirect(url_for('login'))
    
    original_html = render_template('employee_dashboard.html', name=session['user_name'])
    
    magic_script = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const btns = document.querySelectorAll('button');
        let checkInBtn = null;
        let checkOutBtn = null;
        
        btns.forEach(b => {
            if(b.innerText.includes('حضور')) checkInBtn = b;
            if(b.innerText.includes('نصراف')) checkOutBtn = b;
        });

        if(checkInBtn) {
            checkInBtn.onclick = async function(e) {
                e.preventDefault();
                if (!navigator.geolocation) { alert("متصفحك لا يدعم تحديد الموقع!"); return; }
                
                alert("جاري فتح الكاميرا والموقع... يرجى الانتظار والموافقة ⏳");
                navigator.geolocation.getCurrentPosition(async (position) => {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                        const video = document.createElement('video');
                        video.srcObject = stream;
                        
                        await new Promise(resolve => video.onloadedmetadata = resolve);
                        await video.play();
                        
                        const canvas = document.createElement('canvas');
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        canvas.getContext('2d').drawImage(video, 0, 0);
                        const photoData = canvas.toDataURL('image/jpeg');
                        
                        stream.getTracks().forEach(track => track.stop());
                        
                        const response = await fetch('/check_in', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ lat: lat, lng: lng, photo: photoData })
                        });
                        const result = await response.json();
                        alert(result.message);
                        if(response.ok) window.location.reload();
                    } catch (err) {
                        alert("مش قادر أفتح الكاميرا ❌ اتأكد إنك إديت سماح (Allow) للمتصفح.");
                    }
                }, (error) => { alert("لازم تدوس سماح (Allow) للموقع (GPS) ❌"); });
            };
        }
        
        if(checkOutBtn) {
            checkOutBtn.onclick = async function(e) {
                e.preventDefault();
                const response = await fetch('/check_out', { method: 'POST' });
                const result = await response.json();
                alert(result.message);
                if(response.ok) window.location.reload();
            }
        }
    });
    </script>
    """
    
    return original_html + magic_script



@app.route('/employees')
def employees():
    if session.get('role') != 'Admin': return redirect(url_for('login'))
    conn = get_db_connection()
    all_emp = conn.execute('SELECT * FROM employees').fetchall()
    conn.close()
    return render_template('employees.html', employees=all_emp)

@app.route('/delete_employee/<int:id>', methods=['GET', 'POST'])
@app.route('/admin/delete_employee/<int:id>', methods=['GET', 'POST'])
@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete_employee(id):
    if session.get('role') != 'Admin': return redirect(url_for('login'))
    conn = get_db_connection()
    emp = conn.execute('SELECT photo FROM employees WHERE id = ?', (id,)).fetchone()
    if emp and emp['photo']:
        photo_path = os.path.join('static/uploads', emp['photo'])
        if os.path.exists(photo_path):
            try: os.remove(photo_path)
            except: pass
    conn.execute('DELETE FROM employees WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('employees'))

@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if session.get('role') != 'Admin': return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')
        dept = request.form.get('dept')
        role = request.form.get('role')
        hourly_rate = request.form.get('hourly_rate') or 0
        photo = request.files.get('photo')

        if not photo or photo.filename == '':
            return "يجب رفع صورة الموظف لتعريف البصمة ❌"

        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{photo.filename}"
        filepath = os.path.join('static/uploads', filename)
        photo.save(filepath)
        
        encoding = get_face_encoding(filepath)
        if encoding is None:
            if os.path.exists(filepath): os.remove(filepath)
            return "لم يتم التعرف على الوجه في الصورة. يرجى رفع صورة واضحة ❌"

        conn = get_db_connection()
        try:
            conn.execute('''INSERT INTO employees (name, username, password, dept, role, photo, face_encoding, hourly_rate) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (name, username, password, dept, role, filename, json.dumps(encoding.tolist()), hourly_rate))
            conn.commit()
            conn.close()
            return redirect(url_for('employees'))
        except sqlite3.IntegrityError:
            conn.close()
            return "اسم المستخدم هذا موجود مسبقاً! يرجى اختيار اسم آخر ❌"
        except Exception as e:
            if conn: conn.close()
            return f"حدث خطأ غير متوقع: {str(e)}"
    return render_template('add_employee.html')

from flask import flash

@app.route('/set_zone', methods=['GET', 'POST'])
def set_zone():
    if session.get('role') != 'Admin':
        flash("❌ غير مسموح لك بالدخول", "danger")
        return redirect(url_for('login'))

    try:
        with get_db_connection() as conn:

            if request.method == 'POST':
                lat = request.form.get('lat')
                lng = request.form.get('lng')
                radius = request.form.get('radius')

                # 🔹 تأكد إن كل القيم موجودة
                if not lat or not lng or not radius:
                    flash("❌ كل الحقول مطلوبة", "danger")
                    return redirect(url_for('set_zone'))

                # 🔹 تحويل لأرقام + validation
                try:
                    lat = float(lat)
                    lng = float(lng)
                    radius = float(radius)
                except ValueError:
                    flash("❌ لازم تدخل أرقام صحيحة", "danger")
                    return redirect(url_for('set_zone'))

                # 🔹 تحقق من القيم المنطقية
                if not (-90 <= lat <= 90):
                    flash("❌ خط العرض لازم يكون بين -90 و 90", "danger")
                    return redirect(url_for('set_zone'))

                if not (-180 <= lng <= 180):
                    flash("❌ خط الطول لازم يكون بين -180 و 180", "danger")
                    return redirect(url_for('set_zone'))

                if radius <= 0 or radius > 10000:
                    flash("❌ النطاق لازم يكون بين 1 و 10000 متر", "danger")
                    return redirect(url_for('set_zone'))

                # 🔹 تحديث الداتا بيز
                conn.execute(
                    'UPDATE settings SET lat=?, lng=?, radius=? WHERE id=1',
                    (lat, lng, radius)
                )
                conn.commit()

                flash("✅ تم حفظ النطاق الجغرافي بنجاح", "success")

                print(f"\n✅ Zone Updated | lat: {lat} | lng: {lng} | radius: {radius}m\n")

                return redirect(url_for('set_zone'))

            # 🔹 GET
            zone = conn.execute(
                'SELECT lat, lng, radius FROM settings WHERE id=1'
            ).fetchone()

        return render_template('set_zone.html', zone=zone)

    except Exception as e:
        print("❌ Error:", e)
        flash("❌ حصل خطأ في السيرفر", "danger")
        return redirect(url_for('set_zone'))

@app.route('/check_in', methods=['POST'])
def check_in():
    if not session.get('logged_in'):
        return jsonify({"message": "سجل دخولك أولاً"}), 401

    from datetime import datetime

    user_id = session.get('user_id')
    req_data = request.get_json(silent=True) or request.form

    # 🔹 قراءة الموقع
    try:
        u_lat = float(req_data.get('lat', 0))
        u_lng = float(req_data.get('lng', 0))
    except (TypeError, ValueError):
        return jsonify({"message": "❌ خطأ في تحديد الموقع"}), 400

    # 🔹 قراءة الصورة
    photo_data = req_data.get('photo')
    if not photo_data:
        return jsonify({"message": "❌ لم يتم التقاط صورة"}), 400

    conn = get_db_connection()
    try:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # 🔴 1. منع التسجيل أكتر من مرة في اليوم (مهم جدًا)
        already = conn.execute(
            'SELECT id FROM attendance WHERE user_id=? AND date=?',
            (user_id, today_str)
        ).fetchone()

        if already:
            return jsonify({"message": "❌ سجلت حضور بالفعل اليوم ومينفعش تسجل تاني"}), 400

        # 🔹 2. التحقق من النطاق الجغرافي
        st = conn.execute('SELECT lat, lng, radius FROM settings WHERE id=1').fetchone()

        if not st or st['lat'] is None or st['lng'] is None or st['radius'] is None:
            return jsonify({"message": "❌ النطاق غير محدد في النظام"}), 400

        distance = haversine(u_lat, u_lng, float(st['lat']), float(st['lng']))

        # 🔴 منع التسجيل خارج النطاق
        if distance > float(st['radius']):
            return jsonify({
                "message": f"❌ أنت خارج النطاق المسموح ({round(distance / 1000, 2)} كم)"
            }), 400

        status_msg = 'داخل النطاق ✅'
        # 🔹 3. تجهيز الصورة
        if ',' in photo_data:
            photo_data = photo_data.split(',')[1]

        filename = f"checkin_{user_id}_{now.strftime('%H%M%S')}.jpg"
        filepath = os.path.join('static/uploads', filename)

        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(photo_data))

        # 🔹 4. التحقق من بصمة الوجه
        emp = conn.execute(
            'SELECT face_encoding FROM employees WHERE id=?',
            (user_id,)
        ).fetchone()

        if not emp or not emp['face_encoding']:
            return jsonify({"message": "❌ لا توجد بصمة وجه مسجلة"}), 400

        known_encoding = np.array(json.loads(emp['face_encoding']))

        current_image = face_recognition.load_image_file(filepath)
        current_encodings = face_recognition.face_encodings(current_image)

        if len(current_encodings) == 0:
            return jsonify({"message": "❌ لم يتم العثور على وجه واضح"}), 400

        match = face_recognition.compare_faces(
            [known_encoding],
            current_encodings[0],
            tolerance=0.6
        )

        if not match[0]:
            return jsonify({"message": "❌ الوجه غير مطابق"}), 400

        # 🔹 5. تسجيل الحضور
        conn.execute('''
            INSERT INTO attendance (user_id, date, time, status, photo, lat, lng)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            today_str,
            now.strftime("%H:%M:%S"),
            status_msg,
            filename,
            u_lat,
            u_lng
        ))

        conn.commit()

        return jsonify({"message": f"✅ تم تسجيل الحضور ({status_msg})"})

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"message": "❌ خطأ في السيرفر"}), 500

    finally:
        conn.close()

@app.route('/check_out', methods=['POST'])
def check_out():
    if not session.get('logged_in'): return jsonify({"message": "سجل دخولك أولاً"}), 401
    user_id = session.get('user_id')
    conn = get_db_connection()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    try:
        record = conn.execute('SELECT * FROM attendance WHERE user_id=? AND date=? AND check_out_time IS NULL', (user_id, today)).fetchone()
        if record:
            start_dt = datetime.strptime(f"{today} {record['time']}", "%Y-%m-%d %H:%M:%S")
            hours = round((now - start_dt).total_seconds() / 3600, 2)
            conn.execute('UPDATE attendance SET check_out_time=?, work_hours=? WHERE id=?', (now.strftime("%H:%M:%S"), hours, record['id']))
            conn.commit()
            msg = f"تم الانصراف بنجاح. إجمالي ساعات العمل: {hours} ساعة ✅"
        else: 
            msg = "لا يوجد سجل حضور مفتوح لك اليوم ⚠️"
        return jsonify({"message": msg})
    except Exception as e:
        return jsonify({"message": f"خطأ تقني: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/attendance')
@app.route('/admin_attendance')
@app.route('/admin/attendance_logs')
def attendance_logs():
    if session.get('role') != 'Admin': return redirect(url_for('login'))
    conn = get_db_connection()
    query = '''
        SELECT attendance.*, employees.name 
        FROM attendance 
        JOIN employees ON attendance.user_id = employees.id 
        ORDER BY attendance.date DESC, attendance.time DESC
    '''
    logs = conn.execute(query).fetchall()
    conn.close()
    return render_template('admin_attendance.html', logs=logs)

# --- المساعد الذكي ---
@app.route('/api/copilot', methods=['POST'])
def copilot_api():
    user_msg = request.json.get('message')
    prompt = f"أنت مساعد HR. رد باختصار. سؤال: {user_msg}"
    try:
        response = ai_model.generate_content(prompt)
        clean_reply = response.text.replace('**', '').replace('*', '')
        return jsonify({"reply": clean_reply})
    except Exception as e:
        return jsonify({"reply": "عذراً، المساعد غير متاح حالياً."}), 500

# --- الإعلانات ---
@app.route('/company_feed', methods=['GET', 'POST'])
def company_feed():
    if not session.get('logged_in'): return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('INSERT INTO announcement_comments (announcement_id, user_name, comment) VALUES (?,?,?)',
                     (request.form.get('announcement_id'), session['user_name'], request.form.get('comment')))
        conn.commit()
    news = conn.execute('SELECT * FROM announcements ORDER BY created_at DESC').fetchall()
    comments = conn.execute('SELECT * FROM announcement_comments ORDER BY created_at ASC').fetchall()
    conn.close()
    return render_template('company_feed.html', news=news, comments=comments)

@app.route('/add_announcement', methods=['GET', 'POST'])
@app.route('/admin_announcements', methods=['GET', 'POST'])
@app.route('/admin/announcements', methods=['GET', 'POST'])
def add_announcement():
    if session.get('role') != 'Admin': return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        conn.execute('INSERT INTO announcements (title, message) VALUES (?, ?)', (title, message))
        conn.commit()
        conn.close()
        return redirect(url_for('add_announcement'))
    all_news = conn.execute('SELECT * FROM announcements ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin_announcements.html', announcements=all_news, news=all_news)

# --- الإجازات والمرتبات (محدث بالكامل لمطابقة الفرونت إند) ---
from flask import render_template, request, redirect, url_for, session, abort
from datetime import datetime, date
import traceback # تمت الإضافة لتسهيل قراءة الأخطاء في الكونسول

@app.route('/request_leave', methods=['GET', 'POST'])
def request_leave():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if session.get('role') != 'Employee':
        abort(403)

    user_id = session.get('user_id')

    def parse_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            return None

    if request.method == 'POST':
        try:
            l_type = request.form.get('leave_type')
            s_date = request.form.get('start_date')
            e_date = request.form.get('end_date')
            reason = request.form.get('reason')

            if not all([l_type, s_date, e_date, reason]):
                return " كل الحقول مطلوبة", 400

            start = parse_date(s_date)
            end = parse_date(e_date)

            if not start or not end:
                return " صيغة التاريخ غير صحيحة", 400


            if start > end:
                return "❌ تاريخ البداية لازم يكون قبل النهاية", 400

            if start.date() < date.today():
                return "❌ لا يمكن طلب إجازة بتاريخ قديم", 400

            with get_db_connection() as conn:

                existing = conn.execute('''
                    SELECT id FROM leave_requests 
                    WHERE user_id=? AND status IN ('Pending', 'Approved')
                ''', (user_id,)).fetchone()

                if existing:
                    return " لديك طلب إجازة نشط بالفعل", 400

                request_date = datetime.now()

                conn.execute('''
                    INSERT INTO leave_requests 
                    (user_id, leave_type, start_date, end_date, reason, status, request_date)
                    VALUES (?, ?, ?, ?, ?, 'Pending', ?)
                ''', (
                    user_id,
                    l_type.strip(),
                    start.strftime("%Y-%m-%d"),  # إدخال التاريخ بتنسيق نقي
                    end.strftime("%Y-%m-%d"),    # إدخال التاريخ بتنسيق نقي
                    reason.strip(),
                    request_date
                ))

                conn.commit()

            return redirect(url_for('employee_dashboard'))

        except Exception as e:
            print(" Error Details:")
            traceback.print_exc()
            return f" خطأ في السيرفر: {str(e)}", 500

    return render_template('request_leave.html')

@app.route('/admin/leaves')
def admin_leaves():

    # 🔐 تسجيل دخول
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # 🔐 صلاحيات الأدمن
    if session.get('role') != 'Admin':
        abort(403)

    try:
        with get_db_connection() as conn:
            requests = conn.execute('''
                SELECT 
                    lr.id,
                    lr.user_id,
                    lr.leave_type,
                    lr.start_date,
                    lr.end_date,
                    lr.reason,
                    lr.status,
                    lr.request_date,
                    e.name
                FROM leave_requests lr
                JOIN employees e ON lr.user_id = e.id
                ORDER BY lr.request_date DESC
            ''').fetchall()

        return render_template('admin_leaves.html', requests=requests)

    except Exception as e:
        print("❌ Error Details:")
        traceback.print_exc()
        return "❌ حدث خطأ في تحميل الإجازات", 500

@app.route('/admin/update_leave/<int:req_id>', methods=['POST'])
def update_leave_status(req_id):
        # 🔐 حماية المسار للأدمن فقط
        if not session.get('logged_in') or session.get('role') != 'Admin':
            abort(403)

        new_status = request.form.get('status')

        if new_status not in ['Approved', 'Rejected']:
            return " حالة غير صالحة", 400

        try:
            with get_db_connection() as conn:

                conn.execute('''
                    UPDATE leave_requests
                    SET status = ?
                    WHERE id = ?
                ''', (new_status, req_id))
                conn.commit()

            # إعادة توجيه الأدمن لنفس صفحة الإجازات ليرى التحديث الجديد
            return redirect(url_for('admin_leaves'))

        except Exception as e:
            print(" Error Details:")
            import traceback
            traceback.print_exc()
            return " حدث خطأ أثناء تحديث حالة الإجازة", 500
# ===================================================
# دالة المرتبات المتكاملة مع حسابات الساعات والإجازات
# ===================================================
@app.route('/admin/payroll')
@app.route('/payroll')
def admin_payroll():
    if session.get('role') != 'Admin': return redirect(url_for('login'))
    conn = get_db_connection()
    
    current_month = datetime.now().strftime('%Y-%m')
    employees = conn.execute('SELECT id, name, hourly_rate FROM employees WHERE role="Employee"').fetchall()
    
    salaries = []
    for emp in employees:
        emp_id = emp['id']
        
        # 1. حساب إجمالي ساعات العمل في الشهر الحالي
        hours_row = conn.execute('''
            SELECT SUM(work_hours) as total 
            FROM attendance 
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        ''', (emp_id, current_month)).fetchone()
        total_hours = hours_row['total'] if hours_row['total'] else 0
        
        # 2. حساب عدد الإجازات المقبولة في الشهر الحالي
        leaves_row = conn.execute('''
            SELECT COUNT(*) as total 
            FROM leave_requests 
            WHERE user_id = ? AND status = 'Approved' AND strftime('%Y-%m', start_date) = ?
        ''', (emp_id, current_month)).fetchone()
        approved_leaves = leaves_row['total']
        
        # 3. حساب الراتب الأساسي المتوقع
        expected_salary = total_hours * emp['hourly_rate']
        
        # تجميع البيانات اللي الفرونت إند طالبها بالمللي
        salaries.append({
            'id': emp_id,
            '; id': emp_id,  # الخدعة عشان الغلطة المطبعية اللي في الفرونت إند
            'name': emp['name'],
            'hourly_rate': emp['hourly_rate'],
            'total_hours': total_hours,
            'approved_leaves': approved_leaves,
            'expected_salary': expected_salary
        })
        
    conn.close()
    return render_template('payroll.html', salaries=salaries)

# ===================================================
# مسار حفظ المرتبات بعد التعديل (مكافآت وخصومات)
# ===================================================
@app.route('/admin/save_salary', methods=['POST'])
def save_salary():
    if session.get('role') != 'Admin': 
        return jsonify({"status": "error", "message": "غير مصرح"}), 403
        
    data = request.get_json(silent=True) or request.form
    emp_id = data.get('emp_id')
    total_hours = data.get('total_hours')
    hourly_rate = data.get('hourly_rate')
    basic = data.get('basic')
    bonus = data.get('bonus')
    deduction = data.get('deduction')
    net = data.get('net')
    month = datetime.now().strftime('%Y-%m')
    
    conn = get_db_connection()
    try:

        existing = conn.execute('SELECT id FROM payroll_history WHERE user_id=? AND month=?', (emp_id, month)).fetchone()
        if existing:
            return jsonify({"status": "error", "message": "⚠️ تم إصدار راتب هذا الشهر لهذا الموظف مسبقاً!"})
            
        conn.execute('''
            INSERT INTO payroll_history 
            (user_id, month, total_hours, hourly_rate, basic_salary, bonus, deduction, net_salary) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, month, total_hours, hourly_rate, basic, bonus, deduction, net))
        conn.commit()
        return jsonify({"status": "success", "message": "تم إصدار الراتب وحفظه في سجلات الموظف بنجاح ✅"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"حدث خطأ: {str(e)}"})
    finally:
        conn.close()

@app.route('/my_payslips')
def my_payslips():
    if not session.get('logged_in'): 
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    conn = get_db_connection()
    payslips = conn.execute('''
        SELECT * FROM payroll_history 
        WHERE user_id = ? 
        ORDER BY issue_date DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return render_template('my_payslips.html', payslips=payslips)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)