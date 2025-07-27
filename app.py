from flask import Flask, render_template, request, session, redirect, url_for, flash
import cv2
import numpy as np
import face_recognition
import os
from datetime import datetime
from datetime import date
import sqlite3
import json
import pandas as pd
import dlib
from pandas.errors import EmptyDataError
import random
import csv

name="amlan"
app = Flask(__name__)
app.secret_key = 'my$ecretK3y123'  # Secret key for session support

@app.route('/new', methods=['GET', 'POST'])
def new():
    return render_template('index.html')

@app.route('/name', methods=['GET', 'POST'])
def name():
    if request.method=="POST":
        name1=request.form['name1']
        name2=request.form['name2']

        # Create database connection and table if not exists
        conn = sqlite3.connect('information.db')
        conn.execute('''CREATE TABLE IF NOT EXISTS Students
                    (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                     NAME TEXT NOT NULL,
                     ROLL_NO TEXT NOT NULL,
                     REGISTRATION_DATE TEXT NOT NULL,
                     FACE_IMAGE TEXT NOT NULL)''')
        
        # Get current date
        today = date.today()
        reg_date = today.strftime('%Y-%m-%d')
        
        # Generate image filename
        img_name = f"{name1}_{name2}.png"
        img_path = os.path.join('Training images', img_name)
        
        # Insert student data
        conn.execute("INSERT INTO Students (NAME, ROLL_NO, REGISTRATION_DATE, FACE_IMAGE) VALUES (?, ?, ?, ?)",
                    (name1, name2, reg_date, img_name))
        conn.commit()
        conn.close()

        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            return "Error: Could not open camera"

        while True:
            ret, frame = cam.read()
            if not ret:
                print("failed to grab frame")
                break
            cv2.imshow("Press Space to capture image", frame)

            k = cv2.waitKey(1)
            if k%256 == 27:
                # ESC pressed
                print("Escape hit, closing...")
                break
            elif k%256 == 32:
                # SPACE pressed
                if not os.path.exists('Training images'):
                    os.makedirs('Training images')
                cv2.imwrite(img_path, frame)
                print(f"{img_name} written!")
                break

        cam.release()
        cv2.destroyAllWindows()
        return render_template('image.html')
    else:
        return 'All is not well'

@app.route("/",methods=["GET","POST"])
def recognize():
     if request.method=="POST":
        path = 'Training images'
        def load_image_rgb(path):
            img = cv2.imread(path)
            if img is None:
                print(f"Image {path} could not be loaded.")
                return None
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Get student data from database
        conn = sqlite3.connect('information.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT NAME, ROLL_NO, FACE_IMAGE FROM Students")
        students = cur.fetchall()
        conn.close()

        images = []
        classNames = []
        
        # Load images and create class names
        for student in students:
            img_path = os.path.join(path, student['FACE_IMAGE'])
            if os.path.exists(img_path):
                curImg = load_image_rgb(img_path)
                if curImg is not None:
                    images.append(curImg)
                    classNames.append(student['NAME'])
                    print(f"Loaded image for {student['NAME']}")

        print('Class names:', classNames)
        
        def findEncodings(images):
            encodeList = []
            for idx, img in enumerate(images):
                try:
                    face_locations = face_recognition.face_locations(img)
                    if not face_locations:
                        print(f"No face found in image {idx}")
                        continue
                    
                    encode = face_recognition.face_encodings(img, face_locations)
                    if encode:
                        encodeList.append(encode[0])
                        print(f"Successfully encoded face {idx}")
                    else:
                        print(f"Could not encode face {idx}")
                except Exception as e:
                    print(f"Error processing image {idx}: {str(e)}")
                    continue
            return encodeList

        if len(images) == 0:
            print("No valid training images found!")
            return render_template('first.html', error="No training images found. Please register students first.")
        
        encodeListKnown = findEncodings(images)
        if len(encodeListKnown) == 0:
            print("No faces could be encoded from training images!")
            return render_template('first.html', error="No faces could be detected in training images.")
        
        print(f'Successfully encoded {len(encodeListKnown)} faces')

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Could not open webcam!")
            return render_template('first.html', error="Could not access webcam.")

        recognized = False
        while True:
            success, img = cap.read()
            if not success:
                print("Failed to grab frame")
                continue

            imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
            imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

            facesCurFrame = face_recognition.face_locations(imgS)
            encodesCurFrame = face_recognition.face_encodings(imgS, facesCurFrame)

            for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
                matches = face_recognition.compare_faces(encodeListKnown, encodeFace, tolerance=0.6)
                faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
                
                if len(faceDis) > 0:
                    matchIndex = np.argmin(faceDis)
                    if matches[matchIndex]:
                        name = classNames[matchIndex].upper()
                        recognized = True
                        markAttendance(name)
                        markData(name)
                        print(f"Recognized: {name}")
                    else:
                        name = 'Unknown'
                        print("Face not recognized")
                else:
                    name = 'Unknown'
                    print("No matching faces found")

                y1, x2, y2, x1 = faceLoc
                y1, x2, y2, x1 = y1*4, x2*4, y2*4, x1*4
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.rectangle(img, (x1, y2-35), (x2, y2), (0, 255, 0), cv2.FILLED)
                cv2.putText(img, name, (x1+6, y2-6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)

            cv2.imshow('Punch your Attendance', img)
            if cv2.waitKey(1) == 27:  # ESC key
                break

        cap.release()
        cv2.destroyAllWindows()
        return render_template('first.html')
     else:
        return render_template('main.html')


@app.route('/login',methods = ['POST'])
def login():
    #print( request.headers )
    json_data = json.loads(request.data.decode())
    username = json_data['username']
    password = json_data['password']
    #print(username,password)
    df= pd.read_csv('cred.csv')
    if len(df.loc[df['username'] == username]['password'].values) > 0:
        if df.loc[df['username'] == username]['password'].values[0] == password:
            session['username'] = username
            return 'success'
        else:
            return 'failed'
    else:
        return 'failed'
        


@app.route('/checklogin')
def checklogin():
    #print('here')
    if 'username' in session:
        return session['username']
    return 'False'


@app.route('/how', methods=["GET", "POST"])
def how():
    return render_template('form1.html')

@app.route('/data',methods=["GET","POST"])
def data():
    if request.method=="POST":
        today=date.today()
        print(today)
        conn = sqlite3.connect('information.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        print ("Opened database successfully");
        # Ensure Attendance table exists
        cur.execute('''CREATE TABLE IF NOT EXISTS Attendance
                        (NAME TEXT NOT NULL,
                         Time TEXT NOT NULL,
                         Date TEXT NOT NULL)''')
        cursor = cur.execute("SELECT DISTINCT NAME,Time, Date from Attendance where Date=?",(today,))
        rows=cur.fetchall()
        print(rows)
        for line in cursor:
            data1=list(line)
        print ("Operation done successfully");
        conn.close()
        return render_template('form2.html',rows=rows)
    else:
        return render_template('form1.html')


            
@app.route('/whole',methods=["GET","POST"])
def whole():
    conn = sqlite3.connect('information.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM Students ORDER BY NAME ASC")
    rows = cur.fetchall()
    conn.close()
    return render_template('form3.html',rows=rows)

@app.route('/dashboard',methods=["GET","POST"])
def dashboard():
    return render_template('dashboard.html')

@app.route('/registered_students')
def registered_students():
    conn = sqlite3.connect('information.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM Students")
    students = cur.fetchall()
    conn.close()
    return render_template('registered_students.html', students=students)

# Sending Email about the attendance report to the faculties/ parents / etc.
# Not working currently
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

def sendMail():
    mssg=MIMEMultipart()


    server=smtplib.SMTP("smtp.gmail.com",'587')
    server.starttls()
    print("Connected with the server")
    user=input("Enter username:")
    pwd=input("Enter password:")
    server.login(user,pwd)
    print("Login Successful!")
    send=user
    rcv=input("Enter Receiver's Email id:")
    mssg["Subject"] = "Employee Report csv"
    mssg["From"] = user
    mssg["To"] = rcv

    body='''
        <html>
        <body>
         <h1>Employee Quarterly Report</h1>
         <h2>Contains the details of all the employees</h2>
         <p>Do not share confidential information with anyone.</p>
        </body>
        </html>
         '''

    body_part=MIMEText(body,'html')
    mssg.attach(body_part)

    with open("emp.csv",'rb') as f:
        mssg.attach(MIMEApplication(f.read(),Name="emp.csv"))

    server.sendmail(mssg["From"],mssg["To"],mssg.as_string())
   # server.quit()

def markAttendance(name):
    with open('attendance.csv','a+',errors='ignore') as f:
        f.seek(0)
        myDataList = f.readlines()
        nameList = []
        for line in myDataList:
            entry = line.split(',')
            nameList.append(entry[0])
        if name not in nameList:
            now = datetime.now()
            dtString = now.strftime('%H:%M')
            f.writelines(f'\n{name},{dtString}')

def markData(name):
    print("The Attended Person is ",name)
    now = datetime.now()
    dtString = now.strftime('%H:%M')
    today = date.today()
    conn = sqlite3.connect('information.db')
    # Add Duration column if it doesn't exist
    conn.execute('''CREATE TABLE IF NOT EXISTS Attendance
                    (NAME TEXT  NOT NULL,
                     Time  TEXT NOT NULL ,Date TEXT NOT NULL, Duration REAL)''')
    # Generate a random duration for demo (10-40 mins)
    duration = random.uniform(10, 40)
    conn.execute("INSERT or Ignore into Attendance (NAME,Time,Date,Duration) values (?,?,?,?)",(name,dtString,today,duration,))
    conn.commit()  
    conn.close()

# --- STAFF REGISTRATION ---
@app.route('/staff_register', methods=['GET', 'POST'])
def staff_register():
    if request.method == "POST":
        staff_name = request.form['staff_name']
        staff_id = request.form['staff_id']
        # Create staff db/table if not exists
        conn = sqlite3.connect('staff_information.db')
        conn.execute('''CREATE TABLE IF NOT EXISTS Staff
                        (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                         NAME TEXT NOT NULL,
                         STAFF_ID TEXT NOT NULL,
                         REGISTRATION_DATE TEXT NOT NULL,
                         FACE_IMAGE TEXT NOT NULL)''')
        today = date.today()
        reg_date = today.strftime('%Y-%m-%d')
        img_name = f"{staff_name}_{staff_id}.png"
        img_path = os.path.join('Staff images', img_name)
        conn.execute("INSERT INTO Staff (NAME, STAFF_ID, REGISTRATION_DATE, FACE_IMAGE) VALUES (?, ?, ?, ?)",
                    (staff_name, staff_id, reg_date, img_name))
        conn.commit()
        conn.close()
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            return "Error: Could not open camera"
        while True:
            ret, frame = cam.read()
            if not ret:
                print("failed to grab frame")
                break
            cv2.imshow("Press Space to capture image", frame)
            k = cv2.waitKey(1)
            if k%256 == 27:
                break
            elif k%256 == 32:
                if not os.path.exists('Staff images'):
                    os.makedirs('Staff images')
                cv2.imwrite(img_path, frame)
                print(f"{img_name} written!")
                break
        cam.release()
        cv2.destroyAllWindows()
        return render_template('image.html')
    else:
        return render_template('staff_register.html')

# --- STAFF ATTENDANCE ---
@app.route('/staff_attendance', methods=["GET", "POST"])
def staff_attendance():
    if request.method == "POST":
        path = 'Staff images'
        def load_image_rgb(path):
            img = cv2.imread(path)
            if img is None:
                print(f"Image {path} could not be loaded.")
                return None
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Get staff data from db
        conn = sqlite3.connect('staff_information.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT NAME, STAFF_ID, FACE_IMAGE FROM Staff")
        staff_members = cur.fetchall()
        conn.close()
        images = []
        classNames = []
        for staff in staff_members:
            img_path = os.path.join(path, staff['FACE_IMAGE'])
            if os.path.exists(img_path):
                curImg = load_image_rgb(img_path)
                if curImg is not None:
                    images.append(curImg)
                    classNames.append(staff['NAME'])
        def findEncodings(images):
            encodeList = []
            for idx, img in enumerate(images):
                try:
                    face_locations = face_recognition.face_locations(img)
                    if not face_locations:
                        continue
                    encode = face_recognition.face_encodings(img, face_locations)
                    if encode:
                        encodeList.append(encode[0])
                except Exception as e:
                    continue
            return encodeList
        if len(images) == 0:
            return render_template('first.html', error="No staff images found. Please register staff first.")
        encodeListKnown = findEncodings(images)
        if len(encodeListKnown) == 0:
            return render_template('first.html', error="No faces could be detected in staff images.")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return render_template('first.html', error="Could not access webcam.")
        recognized = False
        while True:
            success, img = cap.read()
            if not success:
                continue
            imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
            imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)
            facesCurFrame = face_recognition.face_locations(imgS)
            encodesCurFrame = face_recognition.face_encodings(imgS, facesCurFrame)
            for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
                matches = face_recognition.compare_faces(encodeListKnown, encodeFace, tolerance=0.6)
                faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
                if len(faceDis) > 0:
                    matchIndex = np.argmin(faceDis)
                    if matches[matchIndex]:
                        name = classNames[matchIndex].upper()
                        recognized = True
                        markStaffAttendance(name)
                        markStaffData(name)
                        print(f"Recognized: {name}")
                    else:
                        name = 'Unknown'
                else:
                    name = 'Unknown'
                y1, x2, y2, x1 = faceLoc
                y1, x2, y2, x1 = y1*4, x2*4, y2*4, x1*4
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.rectangle(img, (x1, y2-35), (x2, y2), (0, 255, 0), cv2.FILLED)
                cv2.putText(img, name, (x1+6, y2-6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
            cv2.imshow('Staff Attendance', img)
            if cv2.waitKey(1) == 27:
                break
        cap.release()
        cv2.destroyAllWindows()
        return render_template('first.html')
    else:
        return render_template('main.html')

# --- STAFF ATTENDANCE HELPERS ---
def markStaffAttendance(name):
    with open('staff_attendance.csv','a+',errors='ignore') as f:
        f.seek(0)
        myDataList = f.readlines()
        nameList = []
        for line in myDataList:
            entry = line.split(',')
            nameList.append(entry[0])
        if name not in nameList:
            now = datetime.now()
            dtString = now.strftime('%H:%M')
            f.writelines(f'\n{name},{dtString}')

def markStaffData(name):
    now = datetime.now()
    dtString = now.strftime('%H:%M')
    today = date.today()
    conn = sqlite3.connect('staff_information.db')
    # Add Duration column if it doesn't exist
    conn.execute('''CREATE TABLE IF NOT EXISTS StaffAttendance
                    (NAME TEXT  NOT NULL,
                     Time  TEXT NOT NULL ,Date TEXT NOT NULL, Duration REAL)''')
    # Generate a random duration for demo (10-40 mins)
    duration = random.uniform(10, 40)
    conn.execute("INSERT or Ignore into StaffAttendance (NAME,Time,Date,Duration) values (?,?,?,?)",(name,dtString,today,duration,))
    conn.commit()  
    conn.close()

# --- STAFF DASHBOARD ---
@app.route('/staff_dashboard',methods=["GET","POST"])
def staff_dashboard():
    today=date.today()
    conn = sqlite3.connect('staff_information.db')
    conn.row_factory = sqlite3.Row 
    cur = conn.cursor() 
    cur.execute('''CREATE TABLE IF NOT EXISTS StaffAttendance
                    (NAME TEXT  NOT NULL,
                     Time  TEXT NOT NULL ,Date TEXT NOT NULL)''')
    cursor = cur.execute("SELECT DISTINCT NAME,Time, Date from StaffAttendance")
    rows=cur.fetchall()    
    return render_template('staff_dashboard.html',rows=rows)

@app.route('/admin_dashboard', methods=["GET", "POST"])
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/staff_data', methods=["GET", "POST"])
def staff_data():
    if request.method == "POST":
        today = date.today()
        conn = sqlite3.connect('staff_information.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS StaffAttendance
                        (NAME TEXT NOT NULL,
                         Time TEXT NOT NULL,
                         Date TEXT NOT NULL)''')
        cursor = cur.execute("SELECT DISTINCT NAME,Time, Date from StaffAttendance where Date=?", (today,))
        rows = cur.fetchall()
        conn.close()
        return render_template('staff_data.html', rows=rows)
    else:
        return render_template('staff_data.html', rows=[])

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form['username'].strip()
    password = request.form['pass'].strip()
    print(f"Login attempt: username='{username}', password='{password}'")
    try:
        df = pd.read_csv('cred.csv')
        print('Loaded credentials:')
        print(df)
    except FileNotFoundError:
        return render_template('form1.html', error="Credentials file not found. Please contact the administrator.")
    except EmptyDataError:
        return render_template('form1.html', error="Credentials file is empty or corrupted. Please contact the administrator.")
    # Strip spaces from DataFrame columns
    df['username'] = df['username'].astype(str).str.strip()
    df['password'] = df['password'].astype(str).str.strip()
    if len(df.loc[df['username'] == username]['password'].values) > 0:
        print('Matching username found.')
        print('Expected password:', df.loc[df['username'] == username]['password'].values[0])
        if df.loc[df['username'] == username]['password'].values[0] == password:
            session['username'] = username
            return render_template('admin_dashboard.html')
        else:
            print('Password does not match.')
            return render_template('form1.html', error="Invalid credentials")
    else:
        print('Username not found in credentials.')
        return render_template('form1.html', error="Invalid credentials")

@app.route('/local_dashboard')
def local_dashboard():
    conn = sqlite3.connect('information.db')
    cur = conn.cursor()
    # Ensure Duration column exists
    cur.execute("PRAGMA table_info(Attendance)")
    columns = [col[1] for col in cur.fetchall()]
    if 'Duration' not in columns:
        cur.execute("ALTER TABLE Attendance ADD COLUMN Duration REAL")
        conn.commit()
    # Total students
    cur.execute("SELECT COUNT(*) FROM Students")
    total_students = cur.fetchone()[0]
    # Students present today
    today = date.today().strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(DISTINCT NAME) FROM Attendance WHERE Date=?", (today,))
    students_present = cur.fetchone()[0]
    # Attendance by student (total)
    cur.execute("SELECT NAME, COUNT(*) as count FROM Attendance GROUP BY NAME")
    attendance_by_student = cur.fetchall()
    # Attendance trend (by date)
    cur.execute("SELECT Date, COUNT(DISTINCT NAME) FROM Attendance GROUP BY Date ORDER BY Date")
    attendance_trend = cur.fetchall()
    # Duration by student (average)
    cur.execute("SELECT NAME, AVG(Duration) FROM Attendance WHERE Duration IS NOT NULL GROUP BY NAME")
    duration_by_student = cur.fetchall()
    duration_names = [row[0] for row in duration_by_student]
    duration_values = [round(row[1], 2) for row in duration_by_student]
    # Today's attendance table
    cur.execute("SELECT NAME, Time, Duration FROM Attendance WHERE Date=?", (today,))
    attendance_rows = cur.fetchall()
    conn.close()
    # Prepare data for Plotly
    student_names = [row[0] for row in attendance_by_student]
    student_counts = [row[1] for row in attendance_by_student]
    trend_dates = [row[0] for row in attendance_trend]
    trend_counts = [row[1] for row in attendance_trend]
    return render_template(
        'local_dashboard.html',
        total_students=total_students,
        students_present=students_present,
        attendance_rows=attendance_rows,
        today=today,
        student_names=student_names,
        student_counts=student_counts,
        trend_dates=trend_dates,
        trend_counts=trend_counts,
        duration_names=duration_names,
        duration_values=duration_values
    )

@app.route('/staff_whole', methods=["GET", "POST"])
def staff_whole():
    conn = sqlite3.connect('staff_information.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM Staff")
    rows = cur.fetchall()
    conn.close()
    return render_template('staff_whole.html', rows=rows)

@app.route('/staff_local_dashboard')
def staff_local_dashboard():
    conn = sqlite3.connect('staff_information.db')
    cur = conn.cursor()
    # Ensure Duration column exists
    cur.execute("PRAGMA table_info(StaffAttendance)")
    columns = [col[1] for col in cur.fetchall()]
    if 'Duration' not in columns:
        cur.execute("ALTER TABLE StaffAttendance ADD COLUMN Duration REAL")
        conn.commit()
    # Total staff
    cur.execute("SELECT COUNT(*) FROM Staff")
    total_staff = cur.fetchone()[0]
    # Staff present today
    today = date.today().strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(DISTINCT NAME) FROM StaffAttendance WHERE Date=?", (today,))
    staff_present = cur.fetchone()[0]
    # Attendance by staff (total)
    cur.execute("SELECT NAME, COUNT(*) as count FROM StaffAttendance GROUP BY NAME")
    attendance_by_staff = cur.fetchall()
    # Attendance trend (by date)
    cur.execute("SELECT Date, COUNT(DISTINCT NAME) FROM StaffAttendance GROUP BY Date ORDER BY Date")
    attendance_trend = cur.fetchall()
    # Duration by staff (average)
    cur.execute("SELECT NAME, AVG(Duration) FROM StaffAttendance WHERE Duration IS NOT NULL GROUP BY NAME")
    duration_by_staff = cur.fetchall()
    duration_names = [row[0] for row in duration_by_staff]
    duration_values = [round(row[1], 2) for row in duration_by_staff]
    conn.close()
    # Prepare data for Plotly
    staff_names = [row[0] for row in attendance_by_staff]
    staff_counts = [row[1] for row in attendance_by_staff]
    trend_dates = [row[0] for row in attendance_trend]
    trend_counts = [row[1] for row in attendance_trend]
    return render_template(
        'staff_local_dashboard.html',
        total_staff=total_staff,
        staff_present=staff_present,
        staff_names=staff_names,
        staff_counts=staff_counts,
        trend_dates=trend_dates,
        trend_counts=trend_counts,
        duration_names=duration_names,
        duration_values=duration_values
    )

# --- FEEDBACK HANDLING ---
@app.route('/feedback', methods=['POST'])
def feedback():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    feedback_text = request.form.get('feedback')
    conn = sqlite3.connect('information.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS Feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        feedback TEXT NOT NULL,
        submitted_at TEXT NOT NULL
    )''')
    submitted_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("INSERT INTO Feedback (name, email, phone, feedback, submitted_at) VALUES (?, ?, ?, ?, ?)",
                 (name, email, phone, feedback_text, submitted_at))
    conn.commit()
    conn.close()
    return render_template('thank_you.html')

@app.route('/admin_feedback')
def admin_feedback():
    conn = sqlite3.connect('information.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS Feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        feedback TEXT NOT NULL,
        submitted_at TEXT NOT NULL
    )''')
    cur.execute('SELECT * FROM Feedback ORDER BY submitted_at DESC')
    feedbacks = cur.fetchall()
    conn.close()
    return render_template('admin_feedback.html', feedbacks=feedbacks)

@app.route('/delete_student', methods=['POST'])
def delete_student():
    student_id = request.form.get('student_id')
    if not student_id:
        return redirect('/whole')
    # Get student info before deleting
    conn = sqlite3.connect('information.db')
    cur = conn.cursor()
    cur.execute('SELECT NAME, FACE_IMAGE FROM Students WHERE ID=?', (student_id,))
    row = cur.fetchone()
    student_name = row[0] if row else None
    face_image = row[1] if row else None
    # Delete from database
    cur.execute('DELETE FROM Students WHERE ID=?', (student_id,))
    conn.commit()
    conn.close()
    # Remove from attendance.csv if present
    if student_name:
        try:
            with open('attendance.csv', 'r', newline='', errors='ignore') as infile:
                rows = list(csv.reader(infile))
            with open('attendance.csv', 'w', newline='', errors='ignore') as outfile:
                writer = csv.writer(outfile)
                for row in rows:
                    if row and row[0].strip() != student_name:
                        writer.writerow(row)
        except FileNotFoundError:
            pass
    # Remove face image file
    if face_image:
        img_path = os.path.join('Training images', face_image)
        if os.path.exists(img_path):
            os.remove(img_path)
    return redirect('/whole')

@app.route('/delete_staff', methods=['POST'])
def delete_staff():
    staff_id = request.form.get('staff_id')
    if not staff_id:
        return redirect('/staff_whole')
    # Get staff info before deleting
    conn = sqlite3.connect('staff_information.db')
    cur = conn.cursor()
    cur.execute('SELECT NAME, FACE_IMAGE FROM Staff WHERE ID=?', (staff_id,))
    row = cur.fetchone()
    staff_name = row[0] if row else None
    face_image = row[1] if row else None
    # Delete from database
    cur.execute('DELETE FROM Staff WHERE ID=?', (staff_id,))
    conn.commit()
    conn.close()
    # Remove from staff_attendance.csv if present
    if staff_name:
        try:
            with open('staff_attendance.csv', 'r', newline='', errors='ignore') as infile:
                rows = list(csv.reader(infile))
            with open('staff_attendance.csv', 'w', newline='', errors='ignore') as outfile:
                writer = csv.writer(outfile)
                for row in rows:
                    if row and row[0].strip() != staff_name:
                        writer.writerow(row)
        except FileNotFoundError:
            pass
    # Remove face image file
    if face_image:
        img_path = os.path.join('Staff images', face_image)
        if os.path.exists(img_path):
            os.remove(img_path)
    return redirect('/staff_whole')

if __name__ == '__main__':
    app.run(debug=True)

test_img = np.zeros((100,100,3), dtype=np.uint8)
try:
    detector = dlib.get_frontal_face_detector()
    dets = detector(test_img, 1)
    print("dlib test passed")
except Exception as e:
    print("dlib test failed:", e)



