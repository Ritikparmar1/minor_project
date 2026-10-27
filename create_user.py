
import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "database/campus.db"

name = input("Enter full name: ").strip()
email = input("Enter email: ").strip().lower()
password = input("Create password: ")
role = input("Enter role (student/teacher/admin): ").strip().lower()

if not name or not email or not password:
    print("Error: Name, email, and password are required.")
elif role not in ("student", "teacher", "admin"):
    print("Error: Role must be student, teacher, or admin.")
elif len(password) < 8:
    print("Error: Password must contain at least 8 characters.")
else:
    connection = sqlite3.connect(DATABASE)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        connection.execute(
            """
            INSERT INTO users
                (full_name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                generate_password_hash(password),
                role
            )
        )

        connection.commit()
        print("User created successfully!")

    except sqlite3.IntegrityError:
        print("Error: This email or student code may already exist.")

    except sqlite3.OperationalError as error:
        print("Database error:", error)

    finally:
        connection.close()
