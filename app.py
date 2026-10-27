
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
                SELECT id, full_name, email, password_hash, role,
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

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")
        return render_template("login.html")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        full_name=session.get("full_name"),
        role=session.get("role")
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
        return jsonify({"answer": "Please enter a question."}), 400

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

        # Search for the complete or daily timetable
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

        return jsonify({"answer": answer})

    finally:
        connection.close()


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(debug=True)
