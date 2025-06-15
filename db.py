import os
import sqlite3
from aiogram import types as aio_types
from aiogram.types import user

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'courses.db')

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

with get_db_connection() as conn:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            url TEXT UNIQUE NOT NULL,
            channel_id TEXT NOT NULL DEFAULT '-1002519961960'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL
        )
        """
    )
    # Seed default courses
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM courses")
    if cur.fetchone()["cnt"] == 0:
        conn.executemany(
            "INSERT INTO  courses (name, url) VALUES (?, ?)",
            [("Экспресс-грамматика", "https://t.me/+uKg4xGQ0MDtkMTBi"), ("Путешествия", "https://t.me/+umKj0R00Rb9jNzE6")]
        )
    conn.commit()

# --- Helpers ---
def load_courses_url():
    with get_db_connection() as conn:
        return {row["name"]: row["url"] for row in conn.execute("SELECT name, url FROM courses ORDER BY id")}

def load_courses_id():
    with get_db_connection() as conn:
        return {row['name']: row['channel_id'] for row in conn.execute("SELECT name, channel_id FROM courses ORDER BY id")}


# Record payment only if not exists
def record_payment(user_id: int) -> bool:
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT 1 FROM payments WHERE user_id = ?",
            (user_id, )
        )
        if cur.fetchone(): return True
        else: return False

def update_record_payment(user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO payments (user_id) VALUES (?)",
                (user_id, ))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# Course and support commands

def not_admin(user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            cur = conn.execute("SELECT * FROM admin WHERE user_id = ?",
                         (user_id,))
            if cur.fetchone():
                return False
            return True
    except sqlite3.IntegrityError:
        return False

def add_course_to_db(name: str, url: str, id: str) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO courses (name, url, channel_id) VALUES (?, ?, ?)",
                         (name, url, id))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def rename_course_in_db(old: str, new: str) -> bool:
    with get_db_connection() as conn:
        cur = conn.execute(
            "UPDATE courses SET name = ? WHERE name = ?", (new, old)
        )
        conn.commit()
        return cur.rowcount > 0

def save_new_user(user: aio_types.User):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user.id,))
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO users (user_id, first_name, last_name, username) VALUES (?, ?, ?, ?)",
                (user.id, user.first_name, user.last_name, user.username)
            )
            conn.commit()

def load_support():
    with get_db_connection() as conn:
        support = {row['id']: row['user_id'] for row in conn.execute("SELECT id, user_id FROM courses ORDER BY id")}
        return next(iter(support.values()))

def add_support(user_id: int):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user.id,))
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO support (user_id) VALUES (?)",
                (user_id,)
            )
            conn.commit()

def delete_support(user_id: int):
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM support WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

def get_support():
    with get_db_connection() as conn:
        return {row['id']: row['user_id'] for row in conn.execute("SELECT id, user_id FROM support ORDER BY id")}