
import sqlite3
from werkzeug.security import generate_password_hash

connection = sqlite3.connect("database/campus.db")

temporary_password = "CampusTest@123"
hashed_password = generate_password_hash(temporary_password)

connection.execute("""
    UPDATE users
    SET password_hash = ?
    WHERE id IN (1, 2, 3, 4)
      AND role = 'student'
""", (hashed_password,))

connection.commit()

print("Passwords reset successfully!")

users = connection.execute("""
    SELECT id, full_name, email
    FROM users
    WHERE id IN (1, 2, 3, 4)
""").fetchall()

for user in users:
    print(user)

connection.close()

print("\nTemporary Password:", temporary_password)
