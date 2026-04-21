# CoachKai / NutriBot -- Project Context

## Architecture

Two deployment modes:

1. **Telegram bot** (`bot_telegram.py`) -- python-telegram-bot v20+ polling, aiohttp web server for onboarding form
2. **WhatsApp bot** (`main.py`) -- FastAPI + Twilio webhook, serves onboarding HTML

Both share the same core: `db.py`, `ai.py`, `scheduler.py`, `handlers.py`, `web.py`.

### Entry points

| File | Runtime | What it does |
|------|---------|-------------|
| `bot_telegram.py` | Telegram polling | Registers handlers, starts aiohttp for web onboarding, starts APScheduler |
| `main.py` | FastAPI + uvicorn | Twilio WhatsApp webhook (`POST /webhook`), onboarding webapp (`GET /onboarding`, `POST /api/onboarding/complete`), health check (`GET /health`) |

### Key files

| File | Purpose |
|------|---------|
| `handlers.py` | Telegram command & message handlers |
| `whatsapp_handler.py` | WhatsApp message handler (called from main.py) |
| `ai.py` | All Claude API calls (async) |
| `db.py` | Database layer (Postgres or SQLite) |
| `scheduler.py` | APScheduler jobs: followups, schedule recalc, daily summary, proactive messages |
| `web.py` | aiohttp web app: GET/POST `/onboarding/{token}`, renders form, saves profile |
| `charts.py` | Generates calorie/macro charts (PIL/matplotlib) |
| `pdf_generator.py` | PDF report generation |
| `transcriber.py` | Voice message transcription |
| `nutrition.py` / `nutrition_lookup.py` | Nutrition data helpers |

## Tech Stack

- Python 3.10+
- python-telegram-bot v20+ (async polling)
- FastAPI + Twilio (WhatsApp mode)
- Anthropic Claude API (`claude-3-5-haiku-20241022` for text, `claude-sonnet-4-5` for photos) -- meal analysis, vision, chat, onboarding
- APScheduler AsyncIOScheduler -- background jobs
- PostgreSQL (Railway, via `DATABASE_URL` env var) or SQLite fallback (`nutribot.db`)
- psycopg2 (Postgres), sqlite3 (SQLite)
- aiohttp (web server for Telegram mode onboarding)
- python-dotenv

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token |
| `ANTHROPIC_API_KEY` | Claude API key |
| `DATABASE_URL` | Postgres connection string (if set, uses Postgres; otherwise SQLite) |
| `WEB_BASE_URL` | Public URL prefix for onboarding links (default `http://localhost:8080`) |
| `WEB_PORT` | Port for aiohttp web server (default `8080`) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID (WhatsApp mode) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (WhatsApp mode) |
| `TWILIO_WHATSAPP_NUMBER` | Twilio WhatsApp sender number |

## Phone Number Format

**ALWAYS** normalize phone numbers before any DB operation: digits only, no `+`, no spaces, no dashes.
Use `db.normalize_phone(phone)`.

---

## DB Tables

### `users`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | Auto-increment |
| `telegram_id` | BIGINT UNIQUE NOT NULL | Primary user identifier |
| `name` | TEXT | |
| `age` | INTEGER | |
| `weight_kg` | REAL | |
| `height_cm` | REAL | |
| `goal` | TEXT | `lose_weight`, `gain_muscle`, `maintain`, `eat_healthier` |
| `activity_level` | TEXT | `sedentary`, `lightly_active`, `active`, `very_active` |
| `created_at` | TIMESTAMP/TEXT | |
| `onboarding_complete` | INTEGER | 0 or 1 |
| `profile_text` | TEXT | Markdown identity profile from AI intake |
| `onboarding_history` | TEXT | JSON: onboarding conversation history |
| `intake_history` | TEXT | JSON: intake conversation history (cleared after onboarding) |
| `chat_history` | TEXT | JSON: persisted conversation history |
| `training_schedule` | TEXT | e.g. "gym Tue/Thu/Sat 9am, padel Sundays" |
| `daily_calories` | INTEGER | Custom calorie goal (kcal/day) |
| `dashboard_token` | TEXT | Token for dashboard access |
| `last_seen` | TIMESTAMP/TEXT | Last user interaction |
| `last_proactive_sent` | TIMESTAMP/TEXT | Last proactive message sent |
| `coach_mode` | TEXT | `mentor` (default) or `roaster` |
| `phone` | TEXT | Digits only (normalized) |
| `onboarding_step` | TEXT | Current onboarding step |

### `meals`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | |
| `user_id` | INTEGER FK(users.id) | |
| `telegram_id` | BIGINT | |
| `description` | TEXT | Food description |
| `photo_path` | TEXT | Path to food photo |
| `calories_est` | INTEGER | Estimated calories |
| `meal_type` | TEXT | `breakfast`, `lunch`, `dinner`, `snack` |
| `eaten_at` | TIMESTAMP/TEXT | When the meal was eaten (Argentina TZ) |
| `claude_analysis` | TEXT | Full AI analysis text |
| `proteins_g` | REAL | Default 0 |
| `carbs_g` | REAL | Default 0 |
| `fats_g` | REAL | Default 0 |

### `followups`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | |
| `user_id` | INTEGER FK(users.id) | |
| `sent_at` | TIMESTAMP/TEXT | |
| `message` | TEXT | |
| `type` | TEXT | Followup type identifier |

### `eating_schedule`

Learned average meal times per user per meal type.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | |
| `user_id` | INTEGER FK(users.id) | |
| `meal_type` | TEXT NOT NULL | |
| `avg_hour` | REAL | |
| `avg_minute` | REAL | |
| `confidence` | INTEGER | Default 0 |
| `sample_count` | INTEGER | Default 0 |
| UNIQUE | `(user_id, meal_type)` | |

### `onboarding_tokens`

| Column | Type | Notes |
|--------|------|-------|
| `token` | TEXT PK | URL-safe random token |
| `telegram_id` | BIGINT NOT NULL | |
| `created_at` | TIMESTAMP/TEXT | |

### `workouts`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | |
| `user_id` | INTEGER FK(users.id) | |
| `telegram_id` | BIGINT | |
| `workout_type` | TEXT | running, cycling, gym_strength, etc. |
| `description` | TEXT | |
| `duration_min` | INTEGER | |
| `calories_burned` | INTEGER | |
| `intensity` | TEXT | low, moderate, high, very_high |
| `distance_km` | REAL | |
| `notes` | TEXT | |
| `logged_at` | TIMESTAMP/TEXT | |

### `reminders`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | |
| `telegram_id` | BIGINT NOT NULL | |
| `remind_at` | TIMESTAMP/TEXT NOT NULL | When to send |
| `message` | TEXT NOT NULL | |
| `sent` | BOOLEAN/INTEGER | Default FALSE/0 |
| `created_at` | TIMESTAMP/TEXT | |

### `workout_schedules`

Learned average workout times per user per workout type.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | |
| `user_id` | INTEGER FK(users.id) | |
| `workout_type` | TEXT NOT NULL | |
| `days_of_week` | TEXT | Default '' |
| `avg_hour` | REAL | |
| `avg_minute` | REAL | |
| `avg_duration_min` | INTEGER | Default 60 |
| `confidence` | INTEGER | Default 0 |
| `sample_count` | INTEGER | Default 0 |
| UNIQUE | `(user_id, workout_type)` | |

### `memories`

Episodic memories (facts, preferences, events) per user.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER/SERIAL PK | |
| `telegram_id` | BIGINT NOT NULL | |
| `content` | TEXT NOT NULL | |
| `category` | TEXT | Default 'general'. Values: preference, health, schedule, goal, event, general |
| `created_at` | TIMESTAMP/TEXT | |

---

## DB Functions (db.py) -- Complete List

### Internal helpers (not for direct use)

| Function | Purpose |
|----------|---------|
| `normalize_phone(phone)` | Strip non-digits from phone string |
| `_get_pool()` | Get/create psycopg2 connection pool |
| `get_conn()` | Get a DB connection (Postgres pool or SQLite) |
| `_release(conn)` | Return connection to pool / close |
| `_cur(conn)` | Create cursor (RealDictCursor for PG, default for SQLite) |
| `_q(sql)` | Convert `?` placeholders to `%s` for Postgres |
| `_today_clause(col)` | Returns `(sql_fragment, value)` for filtering a column to today (Argentina TZ) |
| `_rows(rows)` | Convert rows to list of dicts, normalize datetimes to ISO strings |
| `init_db()` | Create all tables + run ALTER TABLE migrations |

### Onboarding tokens

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `create_onboarding_token` | `(telegram_id: int) -> str` | token string | Deletes old token for user first, creates new one |
| `get_telegram_id_by_token` | `(token: str)` | `int` or `None` | Look up telegram_id from token |
| `delete_onboarding_token` | `(token: str)` | None | Delete a used token |

### Dashboard tokens

| Function | Signature | Returns |
|----------|-----------|---------|
| `get_or_create_dashboard_token` | `(telegram_id: int) -> str` | Existing or new hex token |

### Users

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `upsert_user` | `(telegram_id: int, **kwargs)` | None | Insert or update user. kwargs are column=value pairs |
| `get_user_by_phone` | `(phone: str)` | `dict` or `None` | Normalizes phone before lookup |
| `get_user` | `(telegram_id: int)` | `dict` or `None` | Get full user row |
| `get_all_users` | `()` | `list[dict]` | Only users with `onboarding_complete=1` |

### Meals

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `add_meal` | `(user_id, telegram_id, description, photo_path, calories_est, meal_type, claude_analysis, proteins_g=0, carbs_g=0, fats_g=0, eaten_at=None)` | None | If `eaten_at` is None, uses current Argentina time |
| `get_today_meals` | `(telegram_id: int)` | `list[dict]` | Today's meals ordered by eaten_at ASC |
| `delete_meal_by_id` | `(telegram_id: int, meal_id: int) -> bool` | True if deleted | Only deletes if meal belongs to user |
| `delete_last_meal` | `(telegram_id: int) -> str \| None` | Description or None | Deletes most recent meal |
| `get_meals_by_type` | `(user_id: int, meal_type: str, limit=20)` | `list[dict]` | Returns `eaten_at` only, ordered DESC |
| `get_weekly_meals` | `(telegram_id: int, days=7)` | `list[dict]` | Meals from last N days |
| `get_last_meal_time` | `(telegram_id: int)` | `str` or `None` | Timestamp of most recent meal |

### Eating schedule

| Function | Signature | Returns |
|----------|-----------|---------|
| `upsert_eating_schedule` | `(user_id, meal_type, avg_hour, avg_minute, confidence, sample_count)` | None |
| `get_eating_schedules` | `(user_id: int)` | `list[dict]` |
| `get_all_eating_schedules` | `()` | `list[dict]` | Joins with users to include telegram_id |

### Followups

| Function | Signature | Returns |
|----------|-----------|---------|
| `add_followup` | `(user_id: int, message: str, ftype: str)` | None |
| `already_sent_followup_today` | `(user_id: int, ftype: str, meal_type: str=None)` | `bool` |

### User identity / history persistence

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `save_profile_text` | `(telegram_id, profile_text)` | None | Updates `users.profile_text` |
| `save_onboarding_history` | `(telegram_id, history: list)` | None | JSON-serializes to `users.onboarding_history` |
| `get_onboarding_history` | `(telegram_id) -> list` | list | JSON-parses from DB |
| `save_intake_history` | `(telegram_id, history: list)` | None | Persists intake conversation |
| `get_intake_history` | `(telegram_id) -> list` | list | |
| `clear_intake_history` | `(telegram_id)` | None | Sets to NULL |
| `save_chat_history` | `(telegram_id, history: list)` | None | Persists conversation history |
| `get_chat_history` | `(telegram_id) -> list` | list | |

### Workouts

| Function | Signature | Returns |
|----------|-----------|---------|
| `add_workout` | `(user_id, telegram_id, workout_type, description, duration_min, calories_burned, intensity, distance_km=None, notes=None)` | None |
| `get_today_workouts` | `(telegram_id: int)` | `list[dict]` |
| `get_recent_workouts` | `(telegram_id, limit=20)` | `list[dict]` |
| `get_workouts_by_type` | `(user_id, workout_type, limit=20)` | `list[dict]` |
| `upsert_workout_schedule` | `(user_id, workout_type, days_of_week, avg_hour, avg_minute, avg_duration_min, confidence, sample_count)` | None |
| `get_workout_schedules` | `(user_id: int)` | `list[dict]` |
| `get_all_workout_schedules` | `()` | `list[dict]` | Only confidence >= 30, joins users |
| `delete_last_workout` | `(telegram_id: int)` | `str` (description) or `None` |
| `get_weekly_workouts` | `(telegram_id, days=7)` | `list[dict]` |

### Reminders

| Function | Signature | Returns |
|----------|-----------|---------|
| `save_reminder` | `(telegram_id, remind_at_iso: str, message: str) -> int` | reminder ID |
| `get_pending_reminders` | `() -> list` | All unsent reminders where `remind_at <= now` |
| `mark_reminder_sent` | `(reminder_id: int)` | None |

### Memories (episodic)

| Function | Signature | Returns |
|----------|-----------|---------|
| `save_memory` | `(telegram_id, content: str, category='general') -> int` | memory ID |
| `get_memories` | `(telegram_id, limit=20) -> list` | Recent memories DESC |

### Last seen / proactive tracking

| Function | Signature | Returns |
|----------|-----------|---------|
| `update_last_seen` | `(telegram_id: int)` | None |
| `get_last_seen` | `(telegram_id: int)` | `str` or `None` |
| `get_last_proactive_sent` | `(telegram_id: int)` | `datetime` or `None` |
| `update_last_proactive_sent` | `(telegram_id: int)` | None |

---

## AI Functions (ai.py) -- Complete List

### Configuration

| Constant | Value | Notes |
|----------|-------|-------|
| `MODEL_TEXT` | `"claude-3-5-haiku-20241022"` | Text messages, food logging, follow-ups |
| `MODEL_VISION` | `"claude-sonnet-4-5"` | Photo analysis only |
| `_COST_INPUT` | $0.80/MTok | Haiku pricing (approx) |
| `_COST_OUTPUT` | $4.00/MTok | Haiku pricing (approx) |

### Cost tracking

| Function | Purpose |
|----------|---------|
| `reset_turn_cost()` | Reset per-turn cost accumulator to 0 |
| `get_turn_cost() -> float` | Get accumulated cost for current turn |

### Core internal

| Function | Purpose |
|----------|---------|
| `get_client()` | Get/create AsyncAnthropic client singleton |
| `_build_profile_context(user, memories=None) -> str` | Build profile context string from user dict + memories for system prompts |
| `_ask(messages, system=SYSTEM_BASE) -> str` | Low-level Claude API call, accumulates cost, returns text |
| `_get_personality(coach_mode) -> str` | Return personality prompt for 'mentor' or 'roaster' mode |

### Onboarding / Intake

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `intake_turn` | `(history: list, user_message: str) -> dict` | `{"reply": str, "done": False}` or `{"reply": str\|None, "done": True, "profile": dict}` | One turn of intake conversation. Uses `save_user_identity` tool. Profile dict has: identity_markdown, name, age, weight_kg, height_cm, goal, activity_level |
| `force_extract_profile` | `(history: list) -> dict\|None` | dict with name, age, weight_kg, height_cm, goal, activity_level, identity_markdown, reply; or None | Force-extracts profile from conversation history when tool call didn't fire |
| `onboarding_welcome` | `(name: str) -> str` | Welcome message string | |

### Meal plan

| Function | Signature | Returns |
|----------|-----------|---------|
| `generate_meal_plan` | `(user: dict, coach_mode=None) -> dict` | JSON dict with: calories, protein_g, carbs_g, fat_g, summary, tips[], breakfasts[], lunches[], dinners[], snacks[] |

### Main message processing

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `process_message` | `(text, user, history, photo_path=None, coach_mode=None) -> dict` | See return types below | The main handler. Builds full context (today meals, workouts, memories, weekly history, macros, Argentina time). Provides 6 tools to Claude. |

**Return types from `process_message`:**

| `type` value | Dict keys | When |
|-------------|-----------|------|
| `"text"` | `content: str` | Normal text response |
| `"meal"` | `meal: dict, reply: str\|None` | User reported eating (log_meal tool). meal has: detected_food, meal_type, calories, proteins_g, carbs_g, fats_g, tip?, aligned_with_goal?, date_offset? |
| `"workout"` | `workout: dict, reply: str\|None` | User reported workout (log_workout tool). workout has: workout_type, description, duration_min, calories_burned, intensity, distance_km?, notes? |
| `"identity_update"` | `update: dict, reply: str\|None` | Profile update (update_user_identity tool). update has: identity_markdown, reason, weight_kg?, goal?, activity_level?, training_schedule?, daily_calories? |
| `"delete_meal"` | `meal_ids: list[int], reply: str\|None` | Meal deletion (delete_meal tool) |
| `"set_reminder"` | `time_str: str, message: str, reply: str\|None` | Reminder set (set_reminder tool) |
| `"save_memory"` | `content: str, category: str, reply: str\|None` | Memory saved (save_memory tool). Categories: preference, health, schedule, goal, event, general |

### Proactive / scheduled messages

| Function | Signature | Returns | Notes |
|----------|-----------|---------|-------|
| `generate_proactive_message` | `(user, trigger, trigger_info, today_meals, today_workouts, daily_goal, coach_mode=None) -> str` | Message string | Triggers: `pre_meal`, `meal_followup`, `workout_checkin` |
| `generate_checkin_message` | `(user, trigger, memories=None, coach_mode=None) -> str` | Message string | Triggers: `breakfast`, `lunch`, `dinner`, `afternoon`, `inactivity`, `evening_summary` |
| `generate_macro_nudge` | `(user, total_cal, daily_goal, coach_mode=None) -> str` | Message string | 19:00 end-of-day calorie closing nudge |

### Charts / summaries

| Function | Signature | Returns |
|----------|-----------|---------|
| `generate_chart_caption` | `(user, meals, total_cal, daily_goal, coach_mode=None) -> str` | Caption for daily chart |
| `generate_daily_summary` | `(user, meals, coach_mode=None) -> str\|None` | Daily summary text (None if no meals) |
| `get_today_meals_summary` | `(telegram_id: int) -> str` | Brief text summary of today's meals (sync helper) |

---

## AI Tools (defined in ai.py, used by Claude)

These are the tools available to Claude during `process_message`:

1. **`log_meal`** -- Log a meal. Required: detected_food, meal_type, calories, proteins_g, carbs_g, fats_g. Optional: tip, aligned_with_goal, date_offset.
2. **`log_workout`** -- Log a workout. Required: workout_type, description, duration_min, calories_burned, intensity. Optional: distance_km, notes.
3. **`update_user_identity`** -- Update user profile. Required: identity_markdown, reason. Optional: weight_kg, goal, activity_level, training_schedule, daily_calories.
4. **`delete_meal`** -- Delete meals. Required: meal_ids (array of int), reason.
5. **`set_reminder`** -- Set a reminder. Required: time_str (HH:MM 24h), message.
6. **`save_memory`** -- Save episodic memory. Required: content, category.

During `intake_turn`, only one tool is available:

1. **`save_user_identity`** -- Save initial profile. Required: identity_markdown, name, weight_kg, height_cm, goal, activity_level. Optional: age.

---

## Onboarding Flow

1. User sends `/start` in Telegram (or first WhatsApp message)
2. Bot generates onboarding token via `db.create_onboarding_token(telegram_id)`
3. Bot sends link: `{WEB_BASE_URL}/onboarding/{token}`
4. User fills web form at that URL
5. `POST /onboarding/{token}` saves profile via `db.upsert_user()`, sets `onboarding_complete=1`
6. Bot sends welcome message + generates meal plan via `ai.generate_meal_plan()`

Alternative: chat-based intake via `ai.intake_turn()` (conversational profile collection).

## Scheduler Jobs

| Job | Interval | What it does |
|-----|----------|-------------|
| Followup check | Every 5 min | Checks eating_schedule, sends pre-meal or followup reminders if due |
| Schedule recalc | Every 1 hr | Recalculates avg meal/workout times from logged data |
| Daily summary | 21:30 ART | Sends daily nutrition summary to users who logged meals |
| Reminder check | Every 1 min | Checks `reminders` table, sends due reminders |
| Proactive check-in | Varies | Sends check-ins based on inactivity, meal times, etc. |

**Rules:** Requires >= 3 samples of same meal type before calculating schedule. Requires >= 30 confidence to send reminders.

## Coach Modes

| Mode | Personality |
|------|-------------|
| `mentor` (default) | Warm, motivating, celebrates small wins, empathetic |
| `roaster` | Sarcastic, acid humor, pushes hard, never truly mean |

## Tone & Language

- Spanish rioplatense (Argentine), uses "vos" not "tu"
- Semiformal: professional but friendly, no street slang
- Short responses: max 2-3 lines
- Honest about unhealthy food, no false praise
- Emojis used sparingly

## Key Rules for Future Changes

- Phone numbers are stored WITHOUT `+` prefix (digits only). Always use `db.normalize_phone()`.
- `telegram_id` is the primary user identifier across all tables.
- In WhatsApp mode, `telegram_id` is derived from phone hash (see `_phone_to_tid` in `whatsapp_handler.py`).
- **Do NOT invent new `db.*` functions** -- use only what's listed above.
- When adding new DB operations, add them to `db.py` first, then use them.
- All AI functions are async. Cost is tracked per-turn via `_turn_cost`.
- The `_USE_POSTGRES` flag in db.py auto-detects: if `DATABASE_URL` is set, uses Postgres; otherwise SQLite.
- `_q(sql)` converts `?` to `%s` for Postgres -- always wrap SQL with `_q()` in db.py.
- `_today_clause(col)` handles date filtering differences between Postgres and SQLite.
- Argentina timezone (`America/Argentina/Buenos_Aires`) is used for all time-related logic.
- `eaten_at` in meals is set to Argentina time by default in `add_meal()`.
