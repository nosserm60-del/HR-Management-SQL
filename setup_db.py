import sqlite3

conn = sqlite3.connect('hr_system.db')
cursor = conn.cursor()

# 1. جدول الموظفين
cursor.execute('''
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    department TEXT,
    role TEXT NOT NULL
)
''')

# 2. جدول الحضور
cursor.execute('''
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    time TEXT,
    lat REAL,
    lng REAL,
    status TEXT,
    FOREIGN KEY(user_id) REFERENCES employees(id)
)
''')

# 3. جدول إعدادات موقع الشركة
cursor.execute('''
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    office_lat REAL,
    office_lng REAL,
    allowed_radius INTEGER
)
''')

# إضافة بيانات أولية (أدمن وموقع افتراضي)
try:
    cursor.execute("INSERT INTO employees (username, password, name, department, role) VALUES ('admin', '123', 'المدير العام', 'الإدارة', 'Admin')")
    cursor.execute("INSERT OR IGNORE INTO settings (id, office_lat, office_lng, allowed_radius) VALUES (1, 30.0444, 31.2357, 100)")
    conn.commit()
    print("تم تأسيس النظام بنجاح! 🎉")
except:
    print("الجداول موجودة بالفعل.")

conn.close()