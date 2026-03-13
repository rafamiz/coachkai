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
                onboarding_complete INTEGER DEFAULT 0,
                profile_text TEXT,
                onboarding_history TEXT,
                last_seen TEXT
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

        for col in ["profile_text", "onboarding_history"]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
                conn.commit()
            except Exception:
                conn.rollback()

        try:
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP")
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS intake_history TEXT")
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_history TEXT")
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

        c.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                telegram_id BIGINT NOT NULL,
                workout_type TEXT,
                description TEXT,
                duration_min INTEGER,
                calories_burned INTEGER,
                intensity TEXT,
                distance_km REAL,
                notes TEXT,
                logged_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                remind_at TIMESTAMP NOT NULL,
                message TEXT NOT NULL,
                sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS workout_schedules (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                workout_type TEXT NOT NULL,
                days_of_week TEXT DEFAULT '',
                avg_hour REAL,
                avg_minute REAL,
                avg_duration_min INTEGER DEFAULT 60,
                confidence INTEGER DEFAULT 0,
                sample_count INTEGER DEFAULT 0,
                UNIQUE(user_id, workout_type),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
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
                onboarding_complete INTEGER DEFAULT 0,
                profile_text TEXT,
                onboarding_history TEXT,
                intake_history TEXT,
                chat_history TEXT
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

        for col in ["profile_text", "onboarding_history"]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            except Exception:
                pass

        try:
            c.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
        except Exception:
            pass

        try:
            c.execute("ALTER TABLE users ADD COLUMN intake_history TEXT")
        except Exception:
            pass

        try:
            c.execute("ALTER TABLE users ADD COLUMN chat_history TEXT")
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

        c.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                workout_type TEXT,
                description TEXT,
                duration_min INTEGER,
                calories_burned INTEGER,
                intensity TEXT,
                distance_km REAL,
                notes TEXT,
                logged_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                remind_at TEXT NOT NULL,
                message TEXT NOT NULL,
                sent INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS workout_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                workout_type TEXT NOT NULL,
                days_of_week TEXT DEFAULT '',
                avg_hour REAL,
                avg_minute REAL,
                avg_duration_min INTEGER DEFAULT 60,
                confidence INTEGER DEFAULT 0,
                sample_count INTEGER DEFAULT 0,
                UNIQUE(user_id, workout_type),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
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


def delete_meal_by_id(telegram_id: int, meal_id: int) -> bool:
    """Delete a specific meal by ID, only if it belongs to this user."""
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("DELETE FROM meals WHERE id = ? AND telegram_id = ?"), (meal_id, telegram_id))
    deleted = c.rowcount > 0
    conn.commit()
    _release(conn)
    return deleted


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


# --- User identity ---

def save_profile_text(telegram_id: int, profile_text: str):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("UPDATE users SET profile_text = ? WHERE telegram_id = ?"), (profile_text, telegram_id))
    conn.commit()
    _release(conn)


def save_onboarding_history(telegram_id: int, history: list):
    import json
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("UPDATE users SET onboarding_history = ? WHERE telegram_id = ?"),
              (json.dumps(history), telegram_id))
    conn.commit()
    _release(conn)


def get_onboarding_history(telegram_id: int) -> list:
    import json
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT onboarding_history FROM users WHERE telegram_id = ?"), (telegram_id,))
    row = c.fetchone()
    _release(conn)
    if not row:
        return []
    raw = dict(row).get("onboarding_history")
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def save_intake_history(telegram_id: int, history: list):
    """Persist onboarding intake history to DB (survives Railway restarts)."""
    import json
    history_json = json.dumps(history, ensure_ascii=False)
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute(
            "UPDATE users SET intake_history = %s WHERE telegram_id = %s",
            (history_json, telegram_id)
        )
    else:
        c.execute(
            "UPDATE users SET intake_history = ? WHERE telegram_id = ?",
            (history_json, telegram_id)
        )
    conn.commit()
    _release(conn)


def get_intake_history(telegram_id: int) -> list:
    """Load persisted onboarding intake history from DB."""
    import json
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT intake_history FROM users WHERE telegram_id = ?"), (telegram_id,))
    row = c.fetchone()
    _release(conn)
    if row:
        val = dict(row).get("intake_history")
        if val:
            try:
                return json.loads(val)
            except Exception:
                return []
    return []


def clear_intake_history(telegram_id: int):
    """Clear intake history after onboarding is complete."""
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute("UPDATE users SET intake_history = NULL WHERE telegram_id = %s", (telegram_id,))
    else:
        c.execute("UPDATE users SET intake_history = NULL WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    _release(conn)

def save_chat_history(telegram_id: int, history: list) -> None:
    """Persist conversation history to DB (survives Railway/Render restarts)."""
    import json
    data = json.dumps(history, ensure_ascii=False)
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute(
            "UPDATE users SET chat_history = %s WHERE telegram_id = %s",
            (data, telegram_id)
        )
    else:
        c.execute(
            "UPDATE users SET chat_history = ? WHERE telegram_id = ?",
            (data, telegram_id)
        )
    conn.commit()
    _release(conn)


def get_chat_history(telegram_id: int) -> list:
    """Load persisted conversation history from DB."""
    import json
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT chat_history FROM users WHERE telegram_id = ?"), (telegram_id,))
    row = c.fetchone()
    _release(conn)
    if not row or not dict(row).get("chat_history"):
        return []
    try:
        return json.loads(dict(row)["chat_history"])
    except Exception:
        return []



# --- Workouts ---

def add_workout(user_id: int, telegram_id: int, workout_type: str, description: str,
                duration_min: int, calories_burned: int, intensity: str,
                distance_km: float = None, notes: str = None):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        INSERT INTO workouts (user_id, telegram_id, workout_type, description,
                              duration_min, calories_burned, intensity, distance_km, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """), (user_id, telegram_id, workout_type, description,
           duration_min, calories_burned, intensity, distance_km, notes))
    conn.commit()
    _release(conn)


def get_today_workouts(telegram_id: int) -> list:
    conn = get_conn()
    c = _cur(conn)
    date_frag, date_val = _today_clause("logged_at")
    c.execute(
        _q(f"SELECT * FROM workouts WHERE telegram_id = ? AND {date_frag} ORDER BY logged_at ASC"),
        (telegram_id, date_val)
    )
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def get_recent_workouts(telegram_id: int, limit: int = 20) -> list:
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        SELECT * FROM workouts WHERE telegram_id = ?
        ORDER BY logged_at DESC LIMIT ?
    """), (telegram_id, limit))
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def get_workouts_by_type(user_id: int, workout_type: str, limit: int = 20) -> list:
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        SELECT * FROM workouts WHERE user_id = ? AND workout_type = ?
        ORDER BY logged_at DESC LIMIT ?
    """), (user_id, workout_type, limit))
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def upsert_workout_schedule(user_id: int, workout_type: str, days_of_week: str,
                            avg_hour: float, avg_minute: float,
                            avg_duration_min: int, confidence: int, sample_count: int):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        INSERT INTO workout_schedules
            (user_id, workout_type, days_of_week, avg_hour, avg_minute, avg_duration_min, confidence, sample_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, workout_type) DO UPDATE SET
            days_of_week = excluded.days_of_week,
            avg_hour = excluded.avg_hour,
            avg_minute = excluded.avg_minute,
            avg_duration_min = excluded.avg_duration_min,
            confidence = excluded.confidence,
            sample_count = excluded.sample_count
    """), (user_id, workout_type, days_of_week, avg_hour, avg_minute,
           avg_duration_min, confidence, sample_count))
    conn.commit()
    _release(conn)


def get_workout_schedules(user_id: int) -> list:
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT * FROM workout_schedules WHERE user_id = ?"), (user_id,))
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def get_all_workout_schedules() -> list:
    conn = get_conn()
    c = _cur(conn)
    c.execute("""
        SELECT ws.*, u.telegram_id
        FROM workout_schedules ws
        JOIN users u ON u.id = ws.user_id
        WHERE ws.confidence >= 30
    """)
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def delete_last_workout(telegram_id: int):
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("""
        SELECT id, description FROM workouts WHERE telegram_id = ?
        ORDER BY logged_at DESC LIMIT 1
    """), (telegram_id,))
    row = c.fetchone()
    if not row:
        _release(conn)
        return None
    wid = dict(row)["id"]
    desc = dict(row)["description"]
    c.execute(_q("DELETE FROM workouts WHERE id = ?"), (wid,))
    conn.commit()
    _release(conn)
    return desc


# ── Reminders ────────────────────────────────────────────────────────────────

def save_reminder(telegram_id: int, remind_at_iso: str, message: str) -> int:
    """Save a user reminder. remind_at_iso is ISO format datetime string."""
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute(
            "INSERT INTO reminders (telegram_id, remind_at, message) VALUES (%s, %s, %s) RETURNING id",
            (telegram_id, remind_at_iso, message)
        )
        rid = c.fetchone()[0]
    else:
        c.execute(
            "INSERT INTO reminders (telegram_id, remind_at, message) VALUES (?, ?, ?)",
            (telegram_id, remind_at_iso, message)
        )
        rid = c.lastrowid
    conn.commit()
    _release(conn)
    return rid


def get_pending_reminders() -> list:
    """Get all unsent reminders that are due (remind_at <= now in UTC)."""
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute("SELECT * FROM reminders WHERE sent = FALSE AND remind_at AT TIME ZONE 'UTC' <= NOW() AT TIME ZONE 'UTC' ORDER BY remind_at")
    else:
        c.execute("SELECT * FROM reminders WHERE sent = 0 AND remind_at <= datetime('now') ORDER BY remind_at")
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def mark_reminder_sent(reminder_id: int):
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute("UPDATE reminders SET sent = TRUE WHERE id = %s", (reminder_id,))
    else:
        c.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    _release(conn)


# ── Memories (episodic) ───────────────────────────────────────────────────────

def save_memory(telegram_id: int, content: str, category: str = "general") -> int:
    """Save an episodic memory for a user."""
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute(
            "INSERT INTO memories (telegram_id, content, category) VALUES (%s, %s, %s) RETURNING id",
            (telegram_id, content, category)
        )
        mid = c.fetchone()[0]
    else:
        c.execute(
            "INSERT INTO memories (telegram_id, content, category) VALUES (?, ?, ?)",
            (telegram_id, content, category)
        )
        mid = c.lastrowid
    conn.commit()
    _release(conn)
    return mid


def get_memories(telegram_id: int, limit: int = 20) -> list:
    """Get recent memories for a user."""
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q(
        "SELECT * FROM memories WHERE telegram_id = ? ORDER BY created_at DESC LIMIT ?"
    ), (telegram_id, limit))
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def get_weekly_meals(telegram_id: int, days: int = 7) -> list:
    """Get meals from the last N days."""
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute(
            f"SELECT * FROM meals WHERE telegram_id = %s AND eaten_at >= NOW() - INTERVAL '{days} days' ORDER BY eaten_at DESC",
            (telegram_id,)
        )
    else:
        c.execute(
            "SELECT * FROM meals WHERE telegram_id = ? AND eaten_at >= datetime('now', ? || ' days') ORDER BY eaten_at DESC",
            (telegram_id, f"-{days}")
        )
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def get_weekly_workouts(telegram_id: int, days: int = 7) -> list:
    """Get workouts from the last N days."""
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute(
            f"SELECT * FROM workouts WHERE telegram_id = %s AND logged_at >= NOW() - INTERVAL '{days} days' ORDER BY logged_at DESC",
            (telegram_id,)
        )
    else:
        c.execute(
            "SELECT * FROM workouts WHERE telegram_id = ? AND logged_at >= datetime('now', ? || ' days') ORDER BY logged_at DESC",
            (telegram_id, f"-{days}")
        )
    rows = c.fetchall()
    _release(conn)
    return _rows(rows)


def get_last_meal_time(telegram_id: int):
    """Get timestamp of the most recent meal logged."""
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT eaten_at FROM meals WHERE telegram_id = ? ORDER BY eaten_at DESC LIMIT 1"), (telegram_id,))
    row = c.fetchone()
    _release(conn)
    if row:
        return dict(row).get("eaten_at")
    return None

# ── Last seen tracking ────────────────────────────────────────────────────────

def update_last_seen(telegram_id: int):
    """Update the last_seen timestamp for a user."""
    conn = get_conn()
    c = _cur(conn)
    if _USE_POSTGRES:
        c.execute("UPDATE users SET last_seen = NOW() WHERE telegram_id = %s", (telegram_id,))
    else:
        c.execute("UPDATE users SET last_seen = datetime('now') WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    _release(conn)


def get_last_seen(telegram_id: int):
    """Get last_seen timestamp for a user."""
    conn = get_conn()
    c = _cur(conn)
    c.execute(_q("SELECT last_seen FROM users WHERE telegram_id = ?"), (telegram_id,))
    row = c.fetchone()
    _release(conn)
    if row:
        return dict(row).get("last_seen")
    return None
