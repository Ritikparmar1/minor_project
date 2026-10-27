import sqlite3
from pathlib import Path

DATABASE = "database/campus.db"

Path(DATABASE).parent.mkdir(parents=True, exist_ok=True)
connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()


# ---------------- ROOMS ----------------

rooms = [

    ("C-201", "CSE Block", 2, "Classroom"),
    ("C-202", "CSE Block", 2, "Classroom"),
    ("C-203", "CSE Block", 2, "Classroom"),
    ("C-204", "CSE Block", 2, "Classroom"),
    ("C-205", "CSE Block", 2, "Classroom"),

    ("LAB-1", "CSE Block", 2, "Computer Lab"),
    ("LAB-2", "CSE Block", 2, "Computer Lab")

]

for room in rooms:
    cursor.execute("""
        INSERT INTO rooms (room_number, building, floor, room_type)
        SELECT ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM rooms WHERE room_number = ?
        )
    """, (*room, room[0]))


# ---------------- LOCATIONS ----------------

locations = [

    (
        "Central Library",
        "Main Academic Block",
        1,
        "Central library of the college"
    ),

    (
        "CSE Department",
        "CSE Block",
        1,
        "Computer Science and Engineering Department"
    ),

    (
        "CSE Lab 1",
        "CSE Block",
        2,
        "Computer programming laboratory"
    ),

    (
        "Examination Cell",
        "Administrative Block",
        1,
        "Office responsible for examination activities"
    ),

    (
        "Canteen",
        "Main Campus",
        1,
        "College canteen"
    ),

    (
        "Computer Center",
        "CSE Block",
        2,
        "Computer center for students"
    ),

    (
        "Principal Office",
        "Administrative Block",
        1,
        "Office of the college principal"
    ),

    (
        "Seminar Hall",
        "Main Academic Block",
        1,
        "Hall used for seminars and college events"
    ),

    (
        "Admission Cell",
        "Administrative Block",
        1,
        "Office responsible for admission activities"
    )

]

for location in locations:
    cursor.execute("""
        INSERT INTO locations (name, building, floor, description)
        SELECT ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM locations WHERE name = ?
        )
    """, (*location, location[0]))

# ---------------- TIMETABLE ----------------

timetable = [

    ("Monday", "09:00 - 10:00", "TOC", "C-201"),
    ("Monday", "10:00 - 11:00", "DBMS", "C-202"),
    ("Monday", "11:00 - 12:00", "Python", "LAB-1"),

    ("Tuesday", "09:00 - 10:00", "Operating System", "C-203"),
    ("Tuesday", "10:00 - 11:00", "TOC", "C-204"),
    ("Tuesday", "11:00 - 12:00", "Python", "LAB-2"),

    ("Wednesday", "09:00 - 10:00", "DBMS", "C-205"),
    ("Wednesday", "10:00 - 11:00", "Python", "LAB-1"),
    ("Wednesday", "11:00 - 12:00", "Operating System", "C-201"),

    ("Thursday", "09:00 - 10:00", "TOC", "C-202"),
    ("Thursday", "10:00 - 11:00", "DBMS", "C-203"),
    ("Thursday", "11:00 - 12:00", "Python", "LAB-2"),

    ("Friday", "09:00 - 10:00", "Operating System", "C-204"),
    ("Friday", "10:00 - 11:00", "TOC", "C-205"),
    ("Friday", "11:00 - 12:00", "DBMS", "C-202")

]

cursor.executemany("""
    INSERT INTO timetable
    (day, time, subject, room)
    VALUES (?, ?, ?, ?)
""", timetable)


# ---------------- SAVE ----------------

connection.commit()
connection.close()

print("✅ Campus data inserted successfully!")