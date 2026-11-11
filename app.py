from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from io import BytesIO
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from flask import send_file
import qrcode
import base64
from io import BytesIO

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

import sqlite3
import os
import secrets
import hashlib

from datetime import datetime, timedelta, timezone


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "CAMPUSIQ_SECRET_KEY",
    "development-only-change-this-key"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DATABASE = "database/campus.db"


# ---------------- DATABASE CONNECTION ----------------

def get_database():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# ---------------- LOGIN PROTECTION ----------------

def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return wrapped_view


def role_required(*allowed_roles):

    def decorator(view_function):

        @wraps(view_function)
        def wrapped_view(*args, **kwargs):

            if "user_id" not in session:
                return redirect(url_for("login"))

            if session.get("role") not in allowed_roles:
                return "Access denied: You do not have permission.", 403

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


# ---------------- HOME PAGE ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- LOGIN PAGE ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.")
            return render_template("login.html")

        connection = get_database()

        try:
            user = connection.execute(
                """
                SELECT
                    id, full_name, email, password_hash, role,
                    semester, section
                FROM users
                WHERE lower(email) = ?
                """,
                (email,)
            ).fetchone()

        finally:
            connection.close()

        if user and check_password_hash(user["password_hash"], password):

            session.clear()

            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            session["semester"] = user["semester"]
            session["section"] = user["section"]

            if user["role"] == "teacher":
                return redirect(url_for("teacher_dashboard"))

            elif user["role"] == "admin":
                return redirect(url_for("dashboard"))

            else:
                return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

        return render_template("login.html")

    return render_template("login.html")


# ---------------- STUDENT DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():

    return render_template(
        "dashboard.html",
        full_name=session.get("full_name"),
        role=session.get("role")
    )


# ---------------- TEACHER DASHBOARD ----------------

@app.route("/teacher/dashboard")
@login_required
@role_required("teacher")
def teacher_dashboard():

    return render_template(
        "teacher_dashboard.html",
        full_name=session.get("full_name"),
        role=session.get("role")
    )


# ---------------- TEACHER ATTENDANCE PAGE ----------------

@app.route("/teacher/attendance", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def teacher_attendance():

    if request.method == "POST":

        subject = request.form.get("subject", "").strip()
        semester = request.form.get("semester", "").strip()
        section = request.form.get("section", "").strip().upper()
        room = request.form.get("room", "").strip().upper()
        duration = request.form.get("duration", "").strip()

        # Validate required fields

        if not subject or not semester or not section or not duration:

            return render_template(
                "teacher_attendance.html",
                full_name=session.get("full_name"),
                error="Please fill in all required fields."
            )

        # Validate semester and duration

        try:
            semester = int(semester)
            duration = int(duration)

        except ValueError:

            return render_template(
                "teacher_attendance.html",
                full_name=session.get("full_name"),
                error="Invalid semester or QR validity."
            )

        if semester not in range(1, 9) or duration not in (5, 10, 15, 30):

            return render_template(
                "teacher_attendance.html",
                full_name=session.get("full_name"),
                error="Invalid semester or QR validity."
            )

        # Generate secure random QR token

        qr_token = secrets.token_urlsafe(32)

        # Store only token hash in database

        qr_token_hash = hashlib.sha256(
            qr_token.encode()
        ).hexdigest()

        # Set session start and expiry times

        starts_at = datetime.now(timezone.utc)

        expires_at = starts_at + timedelta(minutes=duration)

        connection = get_database()

        try:

            cursor = connection.execute(
                """
                INSERT INTO attendance_sessions
                (
                    teacher_id,
                    subject,
                    semester,
                    section,
                    room,
                    qr_token_hash,
                    starts_at,
                    expires_at,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    session["user_id"],
                    subject,
                    semester,
                    section,
                    room or None,
                    qr_token_hash,
                    starts_at.isoformat(),
                    expires_at.isoformat()
                )
            )

            connection.commit()

            session_id = cursor.lastrowid

        except sqlite3.Error:

            connection.rollback()

            return render_template(
                "teacher_attendance.html",
                full_name=session.get("full_name"),
                error="Unable to create attendance session. Please try again."
            )

        finally:
            connection.close()

        # Generate QR code in memory

        qr_image = qrcode.make(qr_token)

        buffer = BytesIO()

        qr_image.save(buffer, format="PNG")

        qr_code_data = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        # Display QR code

        return render_template(
            "teacher_attendance.html",
            full_name=session.get("full_name"),
            success="Attendance session created successfully!",
            qr_code_data=qr_code_data,
            session_id=session_id,
            subject=subject,
            semester=semester,
            section=section,
            room=room,
            expires_at=expires_at.strftime(
                "%d-%m-%Y %I:%M:%S %p UTC"
            )
        )

    return render_template(
        "teacher_attendance.html",
        full_name=session.get("full_name")
    )


# ---------------- STUDENT ATTENDANCE ----------------

@app.route("/student/attendance", methods=["GET", "POST"])
@login_required
@role_required("student")
def student_attendance():

    error = None
    success = None

    if request.method == "POST":

        qr_token = request.form.get("qr_token", "").strip()

        if not qr_token:

            error = "Please scan or enter the attendance QR code."

        else:

            token_hash = hashlib.sha256(
                qr_token.encode()
            ).hexdigest()

            connection = get_database()

            try:

                attendance = connection.execute(
                    """
                    SELECT
                        id, subject, semester, section, room,
                        expires_at, status
                    FROM attendance_sessions
                    WHERE qr_token_hash = ?
                    """,
                    (token_hash,)
                ).fetchone()

                if attendance is None:

                    error = "Invalid attendance QR code."

                elif attendance["status"] != "active":

                    error = "This attendance session is closed."

                else:

                    expiry_time = datetime.fromisoformat(
                        attendance["expires_at"]
                    )

                    current_time = datetime.now(timezone.utc)

                    if expiry_time <= current_time:

                        connection.execute(
                            """
                            UPDATE attendance_sessions
                            SET status = 'closed'
                            WHERE id = ?
                            """,
                            (attendance["id"],)
                        )

                        connection.commit()

                        error = "This attendance QR code has expired."

                    elif int(session.get("semester") or 0) != attendance["semester"]:

                        error = "Your semester does not match this attendance session."

                    elif (
                        (session.get("section") or "").strip().upper()
                        != attendance["section"].strip().upper()
                    ):

                        error = "Your section does not match this attendance session."

                    else:

                        try:

                            connection.execute(
                                """
                                INSERT INTO attendance_records
                                (
                                    session_id,
                                    student_id,
                                    status,
                                    verification_method,
                                    verified_at
                                )
                                VALUES (?, ?, 'present', 'qr', ?)
                                """,
                                (
                                    attendance["id"],
                                    session["user_id"],
                                    current_time.isoformat()
                                )
                            )

                            connection.commit()

                            success = "Your attendance has been marked successfully!"

                        except sqlite3.IntegrityError:

                            error = "Your attendance has already been recorded."

            except (sqlite3.Error, ValueError, TypeError):

                connection.rollback()

                error = "Something went wrong. Please try again."

            finally:
                connection.close()

    return render_template(
        "student_attendance.html",
        full_name=session.get("full_name"),
        error=error,
        success=success
    )


# ---------------- STUDENT FACE REGISTRATION ----------------

@app.route("/student/face-registration")
@login_required
@role_required("student")
def student_face_registration():

    return render_template(
        "face_registration.html",
        full_name=session.get("full_name")
    )

# ---------------- FACE DETECTION API ----------------

@app.route("/student/face-detection", methods=["POST"])
@login_required
@role_required("student")
def student_face_detection():

    import base64
    import numpy as np
    import cv2

    from flask import jsonify
    from face_recognition.face_utils import detect_faces

    try:
        data = request.get_json(silent=True) or {}

        image_data = data.get("image", "")

        if not image_data:
            return jsonify({
                "success": False,
                "message": "No image received."
            }), 400

        # Remove Base64 image prefix
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(
            image_data,
            validate=True
        )

        if len(image_bytes) > 4 * 1024 * 1024:
            return jsonify({
                "success": False,
                "message": "Image is too large."
            }), 413

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:
            return jsonify({
                "success": False,
                "message": "Invalid image."
            }), 400

        gray, faces = detect_faces(frame)

        face_boxes = [
            {
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h)
            }
            for (x, y, w, h) in faces
        ]

        return jsonify({
            "success": True,
            "face_count": len(face_boxes),
            "faces": face_boxes,
            "message": (
                "Face detected!"
                if len(face_boxes) == 1
                else "Please show only one face."
                if len(face_boxes) > 1
                else "No face detected."
            )
        })

    except Exception as error:

        app.logger.exception("Face detection failed")

        return jsonify({
            "success": False,
            "message": "Face detection failed."
        }), 400
    
# ---------------- FACE REGISTRATION API ----------------


@app.route("/student/face-register", methods=["POST"])
@login_required
@role_required("student")
def student_face_register():

    import base64
    import numpy as np
    import cv2

    from flask import jsonify
    from face_recognition.face_utils import detect_faces

    connection = None

    try:
        data = request.get_json(silent=True) or {}

        # Check student consent
        if data.get("consent") is not True:
            return jsonify({
                "success": False,
                "message": "Please provide consent first."
            }), 400

        image_data = data.get("image", "")

        if not image_data:
            return jsonify({
                "success": False,
                "message": "No image received."
            }), 400

        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(
            image_data,
            validate=True
        )

        if len(image_bytes) > 4 * 1024 * 1024:
            return jsonify({
                "success": False,
                "message": "Image is too large."
            }), 413

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:
            return jsonify({
                "success": False,
                "message": "Invalid image."
            }), 400

        gray, faces = detect_faces(frame)

        # Exactly one face is required
        if len(faces) != 1:
            return jsonify({
                "success": False,
                "message": "Please show exactly one face."
            }), 400

        # Crop detected face
        x, y, w, h = faces[0]
        face_image = gray[y:y+h, x:x+w]

        # Resize face image
        face_image = cv2.resize(
            face_image,
            (200, 200)
        )

        # Encode image as PNG bytes
        success, encoded_image = cv2.imencode(
            ".png",
            face_image
        )

        if not success:
            return jsonify({
                "success": False,
                "message": "Could not process face image."
            }), 400

        face_template = encoded_image.tobytes()

        # Save a NEW face sample
        connection = get_database()

        connection.execute("""
            INSERT INTO face_samples
            (user_id, face_template)
            VALUES (?, ?)
        """, (
            session["user_id"],
            face_template
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Face sample registered successfully!"
        })

    except Exception:

        app.logger.exception("Face registration failed")

        return jsonify({
            "success": False,
            "message": "Face registration failed."
        }), 400

    finally:
        if connection is not None:
            connection.close()




# ---------------- TEACHER ATTENDANCE RECORDS ----------------

@app.route("/teacher/attendance/records")
@login_required
@role_required("teacher")
def teacher_attendance_records():

    connection = get_database()

    try:
        # Automatically close expired attendance sessions
        current_time = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            UPDATE attendance_sessions
            SET status = 'closed'
            WHERE teacher_id = ?
            AND status = 'active'
            AND expires_at <= ?
            """,
            (session["user_id"], current_time)
        )

        connection.commit()

        # Fetch attendance records
        records = connection.execute(
            """
            SELECT
                a.id,
                a.subject,
                a.semester,
                a.section,
                a.room,
                a.starts_at,
                a.expires_at,
                a.status,
                COUNT(ar.id) AS total_present
            FROM attendance_sessions a
            LEFT JOIN attendance_records ar
                ON a.id = ar.session_id
            WHERE a.teacher_id = ?
            GROUP BY a.id
            ORDER BY a.id DESC
            """,
            (session["user_id"],)
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "teacher_attendance_records.html",
        records=records
    )


# ---------------- TEACHER ATTENDANCE SESSION DETAILS ----------------

@app.route("/teacher/attendance/records/<int:session_id>")
@login_required
@role_required("teacher")
def teacher_attendance_session_details(session_id):

    connection = get_database()

    try:

        attendance_session = connection.execute(
            """
            SELECT
                id,
                subject,
                semester,
                section,
                room,
                starts_at,
                status
            FROM attendance_sessions
            WHERE id = ? AND teacher_id = ?
            """,
            (session_id, session["user_id"])
        ).fetchone()

        if attendance_session is None:

            return "Attendance session not found or access denied.", 404

        students = connection.execute(
            """
            SELECT
                u.full_name,
                u.email,
                u.semester,
                u.section,
                ar.status,
                ar.verification_method,
                ar.verified_at
            FROM attendance_records ar
            JOIN users u ON u.id = ar.student_id
            WHERE ar.session_id = ?
            ORDER BY ar.verified_at DESC
            """,
            (session_id,)
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "teacher_attendance_session_details.html",
        attendance_session=attendance_session,
        students=students
    )

# ---------------- STUDENT ATTENDANCE HISTORY ----------------

@app.route("/student/attendance/history")
@login_required
@role_required("student")
def student_attendance_history():

    connection = get_database()

    try:
        records = connection.execute(
            """
            SELECT
                a.id,
                a.subject,
                a.semester,
                a.section,
                a.room,
                ar.status,
                ar.verification_method,
                ar.verified_at
            FROM attendance_records ar
            JOIN attendance_sessions a
                ON ar.session_id = a.id
            WHERE ar.student_id = ?
            ORDER BY ar.verified_at DESC
            """,
            (session["user_id"],)
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "student_attendance_history.html",
        records=records,
        full_name=session["full_name"]
    )


# ---------------- STUDENT ATTENDANCE PERCENTAGE ----------------

@app.route("/student/attendance/percentage")
@login_required
@role_required("student")
def student_attendance_percentage():

    connection = get_database()

    try:
        current_time = datetime.now(timezone.utc).isoformat()

        records = connection.execute(
            """
            SELECT
                a.subject,
                COUNT(DISTINCT a.id) AS total_classes,
                COUNT(
                    DISTINCT CASE
                        WHEN ar.status = 'present' THEN a.id
                    END
                ) AS attended_classes,
                ROUND(
                    100.0 * COUNT(
                        DISTINCT CASE
                            WHEN ar.status = 'present' THEN a.id
                        END
                    ) / COUNT(DISTINCT a.id),
                    2
                ) AS percentage

            FROM attendance_sessions a

            LEFT JOIN attendance_records ar
                ON a.id = ar.session_id
                AND ar.student_id = ?

            WHERE a.semester = ?
            AND a.section = ?
            AND (
                a.status = 'closed'
                OR a.expires_at <= ?
            )

            GROUP BY a.subject
            ORDER BY a.subject
            """,
            (
                session["user_id"],
                session["semester"],
                session["section"],
                current_time
            )
        ).fetchall()

    finally:
        connection.close()

     # Calculate overall attendance summary
    total_classes = sum(record["total_classes"] for record in records)

    attended_classes = sum(
     record["attended_classes"] for record in records
 )

    overall_percentage = (
    round((attended_classes / total_classes) * 100, 2)
    if total_classes > 0 else 0
 )

    return render_template(
    "student_attendance_percentage.html",
    records=records,
    full_name=session["full_name"],
    total_classes=total_classes,
    attended_classes=attended_classes,
    overall_percentage=overall_percentage
    )
# ---------------- STUDENT ATTENDANCE PDF REPORT ----------------

@app.route("/student/attendance/download")
@login_required
@role_required("student")
def download_attendance_report():

    connection = get_database()

    try:
        current_time = datetime.now(timezone.utc).isoformat()

        records = connection.execute(
            """
            SELECT
                a.subject,
                COUNT(DISTINCT a.id) AS total_classes,
                COUNT(
                    DISTINCT CASE
                        WHEN ar.status = 'present' THEN a.id
                    END
                ) AS attended_classes,
                ROUND(
                    100.0 * COUNT(
                        DISTINCT CASE
                            WHEN ar.status = 'present' THEN a.id
                        END
                    ) / COUNT(DISTINCT a.id),
                    2
                ) AS percentage
            FROM attendance_sessions a
            LEFT JOIN attendance_records ar
                ON a.id = ar.session_id
                AND ar.student_id = ?
            WHERE a.semester = ?
            AND a.section = ?
            AND (
                a.status = 'closed'
                OR a.expires_at <= ?
            )
            GROUP BY a.subject
            ORDER BY a.subject
            """,
            (
                session["user_id"],
                session["semester"],
                session["section"],
                current_time
            )
        ).fetchall()

    finally:
        connection.close()

    total_classes = sum(record["total_classes"] for record in records)

    attended_classes = sum(
        record["attended_classes"] for record in records
    )

    overall_percentage = (
        round((attended_classes / total_classes) * 100, 2)
        if total_classes > 0 else 0
    )

    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
    "CampusTitle",
    parent=styles["Title"],
    fontSize=22,
    textColor=colors.HexColor("#1d4ed8"),
    alignment=TA_CENTER,
    spaceAfter=10
   )

    subtitle_style = ParagraphStyle(
    "CampusSubtitle",
    parent=styles["Normal"],
    fontSize=11,
    alignment=TA_CENTER,
    textColor=colors.grey,
    spaceAfter=20
 )

    elements = []

     # Report heading
    elements.append(
    Paragraph("CAMPUS IQ", title_style)
  )

    elements.append(
    Paragraph("STUDENT ATTENDANCE REPORT", subtitle_style)
)

    elements.append(Spacer(1, 15))

    # Student information
    elements.append(
    Paragraph(
        f"<b>Student Name:</b> {session['full_name']}",
        styles["Normal"]
    )
)

    elements.append(Spacer(1, 8))

    elements.append(
    Paragraph(
        f"<b>Overall Attendance:</b> {overall_percentage}%",
        styles["Normal"]
    )
 )

    elements.append(Spacer(1, 8))

    elements.append(
    Paragraph(
        f"<b>Classes Attended:</b> {attended_classes} / {total_classes}",
        styles["Normal"]
    )
     
  )

    elements.append(Spacer(1, 20))

    table_data = [
        [
            "Subject",
            "Attended",
            "Total",
            "Percentage",
            "Status"
        ]
    ]

    for record in records:

        status = (
            "Satisfactory"
            if record["percentage"] >= 75
            else "Low Attendance"
        )

        table_data.append([
            record["subject"],
            str(record["attended_classes"]),
            str(record["total_classes"]),
            f"{record['percentage']}%",
            status
        ])

    report_table = Table(
    table_data,
    repeatRows=1,
    colWidths=[100, 75, 65, 85, 120]
   )

    table_style = [
    # Header design
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

    # Table formatting
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("PADDING", (0, 0), (-1, -1), 10),
]

    # Alternate row backgrounds
    for row_number in range(1, len(table_data)):
     if row_number % 2 == 0:
        table_style.append(
            ("BACKGROUND", (0, row_number), (-1, row_number),
             colors.HexColor("#eff6ff"))
        )
    else:
        table_style.append(
            ("BACKGROUND", (0, row_number), (-1, row_number),
             colors.white)
        )

    # Attendance status colors
    if table_data[row_number][4] == "Satisfactory":
        table_style.append(
            ("TEXTCOLOR", (4, row_number), (4, row_number),
             colors.HexColor("#15803d"))
        )
    else:
        table_style.append(
            ("TEXTCOLOR", (4, row_number), (4, row_number),
             colors.HexColor("#dc2626"))
        )

    report_table.setStyle(TableStyle(table_style))

    elements.append(report_table)


    pdf.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="CampusIQ_Attendance_Report.pdf",
        mimetype="application/pdf"
    )
# ---------------- CLOSE ATTENDANCE SESSION ----------------

@app.route("/teacher/attendance/close/<int:session_id>", methods=["POST"])
@login_required
@role_required("teacher")
def close_attendance_session(session_id):

    connection = get_database()

    try:

        cursor = connection.execute(
            """
            UPDATE attendance_sessions
            SET status = 'closed'
            WHERE id = ?
            AND teacher_id = ?
            AND status = 'active'
            """,
            (session_id, session["user_id"])
        )

        connection.commit()

        if cursor.rowcount == 1:

            flash("Attendance session closed successfully!")

        else:

            flash("Session not found or it is already closed.")

    except sqlite3.Error:

        connection.rollback()

        flash("Unable to close the attendance session.")

    finally:
        connection.close()

    return redirect(
        url_for(
            "teacher_attendance_session_details",
            session_id=session_id
        )
    )


# ---------------- TIMETABLE PAGE ----------------

@app.route("/timetable")
@login_required
def timetable():

    connection = get_database()

    try:

        timetable_data = connection.execute(
            """
            SELECT day, time, subject, room
            FROM timetable
            ORDER BY
                CASE day
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,
                time
            """
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "timetable.html",
        timetable_data=timetable_data
    )


# ---------------- CAMPUS LOCATIONS PAGE ----------------

@app.route("/locations")
@login_required
def locations():

    connection = get_database()

    try:

        locations_data = connection.execute(
            """
            SELECT name, building, floor, description
            FROM locations
            ORDER BY name
            """
        ).fetchall()

    finally:
        connection.close()

    return render_template(
        "locations.html",
        locations_data=locations_data
    )


# ---------------- LOGOUT ----------------

@app.route("/logout")
@login_required
def logout():

    session.clear()

    return redirect(url_for("login"))


# ---------------- CHATBOT ----------------

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    question = data.get("question", "").strip().lower()

    if not question:

        return jsonify({
            "answer": "Please enter a question."
        }), 400

    connection = get_database()

    cursor = connection.cursor()

    try:

        # Search for a room

        if "room" in question:

            words = question.upper().split()

            room_number = None

            for word in words:

                word = word.strip("?.,!")

                if word.startswith("C-") or word.startswith("LAB-"):

                    room_number = word

                    break

            if room_number:

                cursor.execute(
                    "SELECT * FROM rooms WHERE room_number = ?",
                    (room_number,)
                )

                room = cursor.fetchone()

                if room:

                    answer = (
                        f"🏫 {room['room_number']} is in "
                        f"{room['building']}, Floor {room['floor']}. "
                        f"It is a {room['room_type']}."
                    )

                else:

                    answer = f"❌ I could not find room {room_number}."

            else:

                answer = (
                    "🏫 Please provide a room number. "
                    "Example: Where is C-204?"
                )

        # Search for a location

        elif any(word in question for word in [
            "where", "location", "located", "office", "hall",
            "library", "canteen", "department", "center", "lab", "cell"
        ]):

            cursor.execute("SELECT * FROM locations")

            all_locations = cursor.fetchall()

            location = None

            for row in all_locations:

                name = row["name"].lower()

                if name in question:

                    location = row

                    break

            if location:

                answer = (
                    f"📍 <b>{location['name']}</b><br><br>"
                    f"🏢 Building: {location['building']}<br>"
                    f"🏬 Floor: {location['floor']}<br>"
                    f"ℹ️ {location['description']}"
                )

            else:

                answer = (
                    "❌ I could not find that location "
                    "in the campus database."
                )

        # Search for the CSE department

        elif "cse" in question or "department" in question:

            cursor.execute(
                "SELECT * FROM locations WHERE name = ?",
                ("CSE Department",)
            )

            location = cursor.fetchone()

            if location:

                answer = (
                    f"🏢 {location['name']} is located in "
                    f"{location['building']}, Floor {location['floor']}."
                )

            else:

                answer = "❌ CSE Department information is not available."

        # Search for the canteen

        elif "canteen" in question:

            cursor.execute(
                "SELECT * FROM locations WHERE name = ?",
                ("Canteen",)
            )

            location = cursor.fetchone()

            if location:

                answer = (
                    f"🍴 The {location['name']} is located in "
                    f"{location['building']}, Floor {location['floor']}."
                )

            else:

                answer = "❌ Canteen information is not available."

        # Search for a subject timetable

        elif any(subject in question for subject in [
            "toc", "dbms", "python", "operating system"
        ]):

            subjects = {
                "toc": "TOC",
                "dbms": "DBMS",
                "python": "Python",
                "operating system": "Operating System"
            }

            subject = None

            for key, value in subjects.items():

                if key in question:

                    subject = value

                    break

            days = [
                "monday", "tuesday", "wednesday",
                "thursday", "friday"
            ]

            day = None

            for d in days:

                if d in question:

                    day = d.capitalize()

                    break

            if day:

                cursor.execute(
                    """
                    SELECT day, time, subject, room
                    FROM timetable
                    WHERE lower(subject) = lower(?) AND day = ?
                    ORDER BY time
                    """,
                    (subject, day)
                )

            else:

                cursor.execute(
                    """
                    SELECT day, time, subject, room
                    FROM timetable
                    WHERE lower(subject) = lower(?)
                    ORDER BY
                        CASE day
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                        END,
                        time
                    """,
                    (subject,)
                )

            subject_data = cursor.fetchall()

            if subject_data:

                if day:

                    answer = f"📚 <b>{subject} on {day}:</b><br><br>"

                else:

                    answer = f"📚 <b>{subject} Classes:</b><br><br>"

                for row in subject_data:

                    answer += (
                        f"📌 <b>{row['day']}</b> | "
                        f"{row['time']} | "
                        f"🏫 Room: {row['room']}<br>"
                    )

            else:

                if day:

                    answer = (
                        f"❌ {subject} class is not scheduled on {day}."
                    )

                else:

                    answer = f"❌ No classes found for {subject}."

        # Search for complete or daily timetable

        elif (
            "timetable" in question
            or "class" in question
            or any(day in question for day in [
                "monday", "tuesday", "wednesday", "thursday", "friday"
            ])
        ):

            days = [
                "monday", "tuesday", "wednesday",
                "thursday", "friday"
            ]

            day = None

            for d in days:

                if d in question:

                    day = d.capitalize()

                    break

            if day:

                cursor.execute(
                    """
                    SELECT day, time, subject, room
                    FROM timetable
                    WHERE day = ?
                    ORDER BY time
                    """,
                    (day,)
                )

            else:

                cursor.execute(
                    """
                    SELECT day, time, subject, room
                    FROM timetable
                    ORDER BY
                        CASE day
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                        END,
                        time
                    """
                )

            timetable_data = cursor.fetchall()

            if timetable_data:

                if day:

                    answer = f"📅 <b>{day} Timetable:</b><br><br>"

                else:

                    answer = "📅 <b>Your Complete Timetable:</b><br><br>"

                for row in timetable_data:

                    answer += (
                        f"📌 <b>{row['day']}</b> | "
                        f"{row['time']} | {row['subject']} | "
                        f"Room: {row['room']}<br>"
                    )

            else:

                if day:

                    answer = f"❌ No classes found for {day}."

                else:

                    answer = "❌ Timetable information is not available."

        # Greeting

        elif "hello" in question or "hi" in question:

            answer = "Hello! 👋 I am CampusIQ. How can I help you?"

        # Unknown question

        else:

            answer = "🤖 I don't have this information yet."

        return jsonify({
            "answer": answer
        })

    finally:
        connection.close()


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":

    app.run(debug=True)
