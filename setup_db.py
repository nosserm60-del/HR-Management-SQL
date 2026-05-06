import pyodbc

# الاتصال بـ SQL Server
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost;'
    'DATABASE=hr_system;'
    'Trusted_Connection=yes;'
    # لو بتستخدم username/password بدّل السطر فوق بـ:
    # 'UID=sa;PWD=your_password;'
)
cursor = conn.cursor()

# 1. جدول الموظفين
cursor.execute('''
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='employees' AND xtype='U')
CREATE TABLE employees (
    id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(255) UNIQUE NOT NULL,
    password NVARCHAR(255) NOT NULL,
    name NVARCHAR(255) NOT NULL,
    department NVARCHAR(255),
    role NVARCHAR(255) NOT NULL
)
''')

# 2. جدول الحضور
cursor.execute('''
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='attendance' AND xtype='U')
CREATE TABLE attendance (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT,
    date NVARCHAR(50),
    time NVARCHAR(50),
    lat FLOAT,
    lng FLOAT,
    status NVARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES employees(id)
)
''')

# 3. جدول إعدادات موقع الشركة
cursor.execute('''
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='settings' AND xtype='U')
CREATE TABLE settings (
    id INT PRIMARY KEY,
    office_lat FLOAT,
    office_lng FLOAT,
    allowed_radius INT
)
''')

# إضافة بيانات أولية
try:
    cursor.execute('''
        IF NOT EXISTS (SELECT * FROM employees WHERE username = 'admin')
        INSERT INTO employees (username, password, name, department, role)
        VALUES ('admin', '123', 'المدير العام', 'الإدارة', 'Admin')
    ''')
    cursor.execute('''
        IF NOT EXISTS (SELECT * FROM settings WHERE id = 1)
        INSERT INTO settings (id, office_lat, office_lng, allowed_radius)
        VALUES (1, 30.0444, 31.2357, 100)
    ''')
    conn.commit()
    print("تم تأسيس النظام بنجاح! 🎉")
except Exception as e:
    print(f"خطأ: {e}")

cursor.close()
conn.close()
