import sqlite3
import os
import secrets
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")
_USE_POSTGRES = bool(DATABASE_URL)

if _USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    _pool = None

DB_PATH = "nutribot.db"


# --- Connection helpers ---

def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
    return _pool


def get_conn():
    if _USE_POSTGRES:
        return _get_pool().getconn()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _release(conn):
    if _USE_POSTGRES:
        _get_pool().putconn(conn)
    else:
        conn.close()


def _cur(conn):
    if _USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def _q(sql: str) -> str:
    """Convert SQLite ? placeholders to psycopg2 %s."""
    if _USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def _today_clause(col: str):
    """Return (sql_fragment, value) for filtering a timestamp column to today."""
    today = datetime.now().strftime("%Y-%m-%d")
    if _USE_POSTGRES:
        return f"DATE({col}) = ?", today
    return f"{col} LIKE ?", f"{today}%"


def _rows(rows) -> list:
    """Convert rows to dicts, normalising datetime objects to ISO strings."""
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        result.append(d)
    return result


# --- Schema ---

def init_db():
    os.makedirs("photos", exist_ok=True)
    conn = get_conn()
    c = _cur(conn)

    if _USE_POSTGRES:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                name TEXT,
                age INTEGER,
                weight_kg REAL,
                height_cm REAL,
                goal TEXT,
                activity_level TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                onboarding_complete INTEGER DEFAULT 0
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                telegram_id BIGINT NOT NULL,
                description TEXT,
                photo_path TEXT,
                calories_est INTEGER,
                meal_type TEXT,
                eaten_at TIMESTAMP DEFAULT NOW(),
                claude_analysis TEXT,
                proteins_g REAL DEFAULT 0,
                carbs_g REAL DEFAULT 0,
                fats_g REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.commit()

        for col, coltype in [("proteins_g", "REAL"), ("carbs_g", "REAL"), ("fats_g", "REAL")]:
            try:
                c.execute(f"ALTER TABLE meals ADD COLUMN {col} {coltype} DEFAULT 0")
                conn.commit()
            except Exception:
                conn.rollback()

        c.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                sent_at TIMESTAMP DEFAULT NOW(),
                message TEXT,
                type TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS eating_schedule (
                id SERIAL PRIMARY KEY,
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
                telegram_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    else:
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
                proteins_g REAL DEFAULT 0,
                carbs_g REAL DEFAULT 0,
                fats_g REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        for col, coltype in [("proteins_g", "REAL"), ("carbs_g", "REAL"), ("fats_g", "REAL")]:
            try:
                c.execute(f"ALTER TABLE meals ADD COLUMN {col} {coltype} DEFAULT 0")
            except Exception:
                pass

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
    _release(conn)


# --- Onboarding tokens ---

def create_onboarding_token(telegram_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("DELETE FROM onboarding_tokens WHERE telegram_id = ?"), (telegram_id,))
    c.execute(_q("INSERT INTO onboarding_tokens (token, telegram_id) VALUES (?, ?)"), (token, telegram_id))
    conn.commit()
    _release(conn)
    return token


def get_telegram_id_by_token(token: str):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT telegram_id FROM onboarding_tokens WHERE token = ?"), (token,))
    row = c.fetchone()
    _release(conn)
    return row["telegram_id"] if row else None


def delete_onboarding_token(token: str):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("DELETE FROM onboarding_tokens WHERE token = ?"), (token,))
    conn.commit()
    _release(conn)


# --- Users ---

def upsert_user(telegram_id: int, **kwargs):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT id FROM users WHERE telegram_id = ?"), (telegram_id,))
    row = c.fetchone()
    if row:
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [telegram_id]
            c.execute(_q(f"UPDATE users SET {sets} WHERE telegram_id = ?"), vals)
    else:
        c.execute(_q("INSERT INTO users (telegram_id) VALUES (?)"), (telegram_id,))
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [telegram_id]
            c.execute(_q(f"UPDATE users SET {sets} WHERE telegram_id = ?"), vals)
    conn.commit()
    _release(conn)


def get_user(telegram_id: int):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT * FROM users WHERE telegram_id = ?"), (telegram_id,))
    row = c.fetchone()
    _release(conn)
    return dict(row) if row else None


def get_all_users():
    conn = get_conn()
    c = _cur(conn)
    c.execute("SELECT * FROM users WHERE onboarding_complete = 1")
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


# --- Meals ---

def add_meal(user_id: int, telegram_id: int, description: str, photo_path: str,
             calories_est: int, meal_type: str, claude_analysis: str,
             proteins_g: float = 0, carbs_g: float = 0, fats_g: float = 0):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        INSERT INTO meals (user_id, telegram_id, description, photo_path, calories_est, meal_type, claude_analysis, proteins_g, carbs_g, fats_g)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """), (user_id, telegram_id, description, photo_path, calories_est, meal_type, claude_analysis,
           proteins_g or 0, carbs_g or 0, fats_g or 0))
    conn.commit()
    _release(conn)


def get_today_meals(telegram_id: int):
    conn = get_conn()
    c = _cur(conn)
    date_frag, date_val = _today_clause("eaten_at")
    c.execute(
        _q(f"SELECT * FROM meals WHERE telegram_id = ? AND {date_frag} ORDER BY eaten_at ASC"),
        (telegram_id, date_val)
    )
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def delete_last_meal(telegram_id: int) -> str | None:
    """Delete the most recent meal for a user. Returns description or None."""
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        SELECT id, description FROM meals
        WHERE telegram_id = ?
        ORDER BY eaten_at DESC
        LIMIT 1
    """), (telegram_id,))
    row = c.fetchone()
    if not row:
        _release(conn)
        return None
    meal_id = dict(row)["id"]
    description = dict(row)["description"]
    c.execute(_q("DELETE FROM meals WHERE id = ?"), (meal_id,))
    conn.commit()
    _release(conn)
    return description


def get_meals_by_type(user_id: int, meal_type: str, limit: int = 20):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        SELECT eaten_at FROM meals
        WHERE user_id = ? AND meal_type = ?
        ORDER BY eaten_at DESC
        LIMIT ?
    """), (user_id, meal_type, limit))
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


# --- Eating schedule ---

def upsert_eating_schedule(user_id: int, meal_type: str, avg_hour: float,
                           avg_minute: float, confidence: int, sample_count: int):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        INSERT INTO eating_schedule (user_id, meal_type, avg_hour, avg_minute, confidence, sample_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, meal_type) DO UPDATE SET
            avg_hour = excluded.avg_hour,
            avg_minute = excluded.avg_minute,
            confidence = excluded.confidence,
            sample_count = excluded.sample_count
    """), (user_id, meal_type, avg_hour, avg_minute, confidence, sample_count))
    conn.commit()
    _release(conn)


def get_eating_schedules(user_id: int):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT * FROM eating_schedule WHERE user_id = ?"), (user_id,))
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def get_all_eating_schedules():
    conn = get_conn()
    c = _cur(conn)
    c.execute("""
        SELECT es.*, u.telegram_id
        FROM eating_schedule es
        JOIN users u ON u.id = es.user_id
        WHERE es.confidence >= 30
    """)
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


# --- Followups ---

def add_followup(user_id: int, message: str, ftype: str):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("INSERT INTO followups (user_id, message, type) VALUES (?, ?, ?)"),
              (user_id, message, ftype))
    conn.commit()
    _release(conn)


def already_sent_followup_today(user_id: int, ftype: str, meal_type: str = None):
    conn = get_conn()
    c = _cur(conn)
    msg_filter = f"%{meal_type}%" if meal_type else "%"
    date_frag, date_val = _today_clause("sent_at")
    c.execute(
        _q(f"SELECT id FROM followups WHERE user_id = ? AND type = ? AND {date_frag} AND message LIKE ? LIMIT 1"),
        (user_id, ftype, date_val, msg_filter)
    )
    row = c.fetchone()
    _release(conn)
    return row is not None
