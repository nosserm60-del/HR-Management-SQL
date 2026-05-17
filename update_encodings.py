import face_recognition
import json
import pyodbc
import os

UPLOAD_FOLDER = 'static/uploads'

conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=.\\SQLEXPRESS01;'
    'DATABASE=hr_system;'
    'Trusted_Connection=yes;'
)
cursor = conn.cursor()

cursor.execute("SELECT id, name, photo FROM employees WHERE photo != '' AND face_encoding IS NULL")
employees = cursor.fetchall()

for emp in employees:
    filepath = os.path.join(UPLOAD_FOLDER, emp.photo)
    if not os.path.exists(filepath):
        print(f"❌ الصورة مش موجودة: {emp.name}")
        continue
    
    image = face_recognition.load_image_file(filepath)
    encodings = face_recognition.face_encodings(image)
    
    if encodings:
        encoding_json = json.dumps(encodings[0].tolist())
        cursor.execute("UPDATE employees SET face_encoding=? WHERE id=?", (encoding_json, emp.id))
        conn.commit()
        print(f"✅ تم تحديث: {emp.name}")
    else:
        print(f"⚠️ مفيش وجه في صورة: {emp.name}")

conn.close()
print("✅ انتهى!")