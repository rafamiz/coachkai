import sqlite3
import os
import secrets
from datetime import datetime

DB_PATH = "nutribot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs("photos", exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            age INTEGER,
            weight_kg REAL,
            height_cm REAL,
            goal TEXT,
            activity_level TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            onboarding_complete INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            description TEXT,
            photo_path TEXT,
            calories_est INTEGER,
            meal_type TEXT,
            eaten_at TEXT DEFAULT (datetime('now')),
            claude_analysis TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sent_at TEXT DEFAULT (datetime('now')),
            message TEXT,
            type TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS eating_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            meal_type TEXT NOT NULL,
            avg_hour REAL,
            avg_minute REAL,
            confidence INTEGER DEFAULT 0,
            sample_count INTEGER DEFAULT 0,
            UNIQUE(user_id, meal_type),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_tokens (
            token TEXT PRIMARY KEY,
            telegram_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# --- Onboarding tokens ---

def create_onboarding_token(telegram_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM onboarding_tokens WHERE telegram_id = ?", (telegram_id,))
    c.execute("INSERT INTO onboarding_tokens (token, telegram_id) VALUES (?, ?)", (token, telegram_id))
    conn.commit()
    conn.close()
    return token


def get_telegram_id_by_token(token: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM onboarding_tokens WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    return row["telegram_id"] if row else None


def delete_onboarding_token(token: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM onboarding_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# --- Users ---

def upsert_user(telegram_id: int, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    row = c.fetchone()
    if row:
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [telegram_id]
            c.execute(f"UPDATE users SET {sets} WHERE telegram_id = ?", vals)
    else:
        c.execute("INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,))
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [telegram_id]
            c.execute(f"UPDATE users SET {sets} WHERE telegram_id = ?", vals)
    conn.commit()
    conn.close()


def get_user(telegram_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE onboarding_complete = 1")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Meals ---

def add_meal(user_id: int, telegram_id: int, description: str, photo_path: str,
             calories_est: int, meal_type: str, claude_analysis: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO meals (user_id, telegram_id, description, photo_path, calories_est, meal_type, claude_analysis)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, telegram_id, description, photo_path, calories_est, meal_type, claude_analysis))
    conn.commit()
    conn.close()


def get_today_meals(telegram_id: int):
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("""
        SELECT * FROM meals
        WHERE telegram_id = ? AND eaten_at LIKE ?
        ORDER BY eaten_at ASC
    """, (telegram_id, f"{today}%"))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_meals_by_type(user_id: int, meal_type: str, limit: int = 20):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT eaten_at FROM meals
        WHERE user_id = ? AND meal_type = ?
        ORDER BY eaten_at DESC
        LIMIT ?
    """, (user_id, meal_type, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Eating schedule ---

def upsert_eating_schedule(user_id: int, meal_type: str, avg_hour: float,
                           avg_minute: float, confidence: int, sample_count: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO eating_schedule (user_id, meal_type, avg_hour, avg_minute, confidence, sample_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, meal_type) DO UPDATE SET
            avg_hour = excluded.avg_hour,
            avg_minute = excluded.avg_minute,
            confidence = excluded.confidence,
            sample_count = excluded.sample_count
    """, (user_id, meal_type, avg_hour, avg_minute, confidence, sample_count))
    conn.commit()
    conn.close()


def get_eating_schedules(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM eating_schedule WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_eating_schedules():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT es.*, u.telegram_id
        FROM eating_schedule es
        JOIN users u ON u.id = es.user_id
        WHERE es.confidence >= 30
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Followups ---

def add_followup(user_id: int, message: str, ftype: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO followups (user_id, message, type) VALUES (?, ?, ?)",
              (user_id, message, ftype))
    conn.commit()
    conn.close()


def already_sent_followup_today(user_id: int, ftype: str, meal_type: str = None):
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    msg_filter = f"%{meal_type}%" if meal_type else "%"
    c.execute("""
        SELECT id FROM followups
        WHERE user_id = ? AND type = ? AND sent_at LIKE ? AND message LIKE ?
        LIMIT 1
    """, (user_id, ftype, f"{today}%", msg_filter))
    row = c.fetchone()
    conn.close()
    return row is not None
