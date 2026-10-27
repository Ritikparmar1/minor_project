import sqlite3
import os

DATABASE = "database/campus.db"


def create_database():

    # Create database folder if it does not exist
    os.makedirs("database", exist_ok=True)

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # Create rooms table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            building TEXT NOT NULL,
            floor INTEGER,
            room_type TEXT
        )
    """)

    # Create locations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            building TEXT,
            floor INTEGER,
            description TEXT
        )
    """)

          # Create timetable table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            time TEXT NOT NULL,
            subject TEXT NOT NULL,
            room TEXT NOT NULL
        )
    """)

    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code TEXT UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (
                role IN ('student', 'teacher', 'admin')
            ),
            semester INTEGER,
            section TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create face profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS face_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            face_template BLOB NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create attendance sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            semester INTEGER NOT NULL,
            section TEXT NOT NULL,
            room TEXT,
            qr_token_hash TEXT NOT NULL UNIQUE,
            starts_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'closed')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id)
        )
    """)

    # Create attendance records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'present'
                CHECK (status IN ('present', 'absent', 'pending_review')),
            verification_method TEXT,
            verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id)
                REFERENCES attendance_sessions(id),
            FOREIGN KEY (student_id)
                REFERENCES users(id),
            UNIQUE (session_id, student_id)
        )
    """)

    # Create classroom verification log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presence_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            result TEXT NOT NULL,
            checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id)
                REFERENCES attendance_sessions(id),
            FOREIGN KEY (student_id)
                REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()

    print("Database created successfully!")



if __name__ == "__main__":
    create_database()