import logging
from collections import Counter
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

ART = ZoneInfo("America/Argentina/Buenos_Aires")

import db
import ai
import charts

logger = logging.getLogger(__name__)

_bot_app = None
_scheduler = None

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]

PROACTIVE_COOLDOWN_MINUTES = 45


async def _can_send_proactive(telegram_id: int) -> bool:
    """Returns True if enough time has passed since last proactive message."""
    last = db.get_last_proactive_sent(telegram_id)
    if last is None:
        return True
    import pytz
    from datetime import timedelta
    BA_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(BA_TZ)
    if last.tzinfo is None:
        last = BA_TZ.localize(last)
    return (now - last) >= timedelta(minutes=PROACTIVE_COOLDOWN_MINUTES)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler(app):
    global _bot_app, _scheduler
    _bot_app = app
    _scheduler = AsyncIOScheduler(timezone=ART)
    _scheduler.add_job(check_proactive_messages, "interval", minutes=5,  id="proactive_check")
    _scheduler.add_job(analyze_all_patterns,     "interval", hours=1,    id="pattern_analysis")
    _scheduler.add_job(send_daily_summaries,     "cron",     hour=21, minute=0, id="daily_summary")
    _scheduler.add_job(check_reminders,          "interval", minutes=1,  id="reminders_check")
    _scheduler.add_job(check_meal_absence,       "interval", minutes=30, id="absence_check")
    # Proactive meal check-ins (Argentina time via ART timezone scheduler)
    _scheduler.add_job(send_meal_checkin, "cron", hour=8,  minute=30, args=["breakfast"], id="breakfast_checkin")
    _scheduler.add_job(send_meal_checkin, "cron", hour=13, minute=0,  args=["lunch"],     id="lunch_checkin")
    _scheduler.add_job(send_meal_checkin, "cron", hour=17, minute=0,  args=["snack"],     id="snack_checkin")
    _scheduler.add_job(send_meal_checkin, "cron", hour=20, minute=30, args=["dinner"],    id="dinner_checkin")
    _scheduler.add_job(check_training_reminders, "interval", minutes=5, id="training_reminders")
    # Inactivity check every hour
    _scheduler.add_job(send_inactivity_checkin, "interval", hours=1, id="inactivity_check")
    _scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)


def get_bot_app():
    return _bot_app


# ---------------------------------------------------------------------------
# Pattern analysis — meals
# ---------------------------------------------------------------------------

def update_eating_schedule(user_id: int, meal_type: str):
    meals = db.get_meals_by_type(user_id, meal_type, limit=20)
    if len(meals) < 3:
        return
    hours = []
    for m in meals:
        try:
            dt = datetime.fromisoformat(m["eaten_at"])
            hours.append(dt.hour + dt.minute / 60.0)
        except Exception:
            continue
    if len(hours) < 3:
        return
    avg = sum(hours) / len(hours)
    avg_hour   = int(avg)
    avg_minute = (avg - avg_hour) * 60
    confidence = min(100, len(hours) * 10)
    db.upsert_eating_schedule(user_id, meal_type, avg_hour, avg_minute, confidence, len(hours))


# ---------------------------------------------------------------------------
# Pattern analysis — workouts
# ---------------------------------------------------------------------------

def update_workout_schedule(user_id: int, workout_type: str):
    """Detect time + day-of-week pattern for a given workout type."""
    workouts = db.get_workouts_by_type(user_id, workout_type, limit=15)
    if len(workouts) < 3:
        return

    hours, weekdays, durations = [], [], []
    for w in workouts:
        try:
            dt = datetime.fromisoformat(w["logged_at"])
            hours.append(dt.hour + dt.minute / 60.0)
            weekdays.append(dt.weekday())   # 0=Monday … 6=Sunday
            if w.get("duration_min"):
                durations.append(int(w["duration_min"]))
        except Exception:
            continue

    if len(hours) < 3:
        return

    avg_h     = sum(hours) / len(hours)
    avg_hour  = int(avg_h)
    avg_min   = (avg_h - avg_hour) * 60
    avg_dur   = int(sum(durations) / len(durations)) if durations else 60

    # Days with ≥40% frequency are "consistent" training days
    total = len(weekdays)
    day_counts = Counter(weekdays)
    dominant_days = sorted(d for d, c in day_counts.items() if c / total >= 0.4)
    days_str = ",".join(map(str, dominant_days))

    confidence = min(100, len(workouts) * 7)
    db.upsert_workout_schedule(
        user_id, workout_type, days_str,
        avg_hour, avg_min, avg_dur, confidence, len(workouts)
    )


# ---------------------------------------------------------------------------
# Hourly pattern recalculation for all users
# ---------------------------------------------------------------------------

def analyze_all_patterns():
    users = db.get_all_users()
    for user in users:
        uid = user["id"]
        for meal_type in MEAL_TYPES:
            update_eating_schedule(uid, meal_type)
        # Reanalyze all workout types this user has logged
        recent = db.get_recent_workouts(user["telegram_id"], limit=50)
        for wtype in {w["workout_type"] for w in recent if w.get("workout_type")}:
            update_workout_schedule(uid, wtype)


# ---------------------------------------------------------------------------
# Default schedules for new users
# ---------------------------------------------------------------------------

DEFAULT_MEAL_SCHEDULES = {
    "breakfast": (8, 30),
    "lunch":     (12, 30),
    "dinner":    (20, 30),
    "snack":     (16, 0),
}


def seed_default_schedules(user_id: int):
    for meal_type, (hour, minute) in DEFAULT_MEAL_SCHEDULES.items():
        db.upsert_eating_schedule(user_id, meal_type, hour, minute, confidence=0, sample_count=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minutes(hour: float, minute: float) -> int:
    return int(hour) * 60 + int(minute)


def _parse_training_schedule(training_schedule: str):
    """
    Parse training schedule text into list of dicts with weekday/hour/minute.
    weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
    Returns list of dicts: [{"weekday": int, "hour": int, "minute": int}]
    """
    if not training_schedule:
        return []

    day_map = {
        "lunes": 0, "lu": 0, "monday": 0,
        "martes": 1, "ma": 1, "tuesday": 1,
        "mi\u00e9rcoles": 2, "mie": 2, "miercoles": 2, "wednesday": 2,
        "jueves": 3, "ju": 3, "thursday": 3,
        "viernes": 4, "vi": 4, "friday": 4,
        "s\u00e1bado": 5, "sabado": 5, "sa": 5, "saturday": 5,
        "domingo": 6, "do": 6, "sunday": 6,
    }

    import re
    text = training_schedule.lower()

    # Find time: HH:MM or "9am" or "9 hs" or "9h" or "9 de la ma\u00f1ana"
    time_match = re.search(
        r'(\d{1,2}):(\d{2})(?:am|pm)?|(\d{1,2})\s*(?:am|hs|h\b|de la ma\u00f1ana)',
        text
    )
    hour, minute = 9, 0  # default
    if time_match:
        if time_match.group(1):
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
        elif time_match.group(3):
            hour = int(time_match.group(3))
            minute = 0

    # Find days
    found_days = []
    for day_name, day_num in day_map.items():
        if day_name in text and day_num not in found_days:
            found_days.append(day_num)

    return [{"weekday": d, "hour": hour, "minute": minute} for d in sorted(found_days)]


def _near(current_min: int, target_min: int, window: int = 4) -> bool:
    diff = abs(current_min - target_min) % 1440
    return diff <= window or diff >= (1440 - window)


def _day_matches(days_str: str, weekday: int) -> bool:
    """Return True if today's weekday is in the pattern (empty = all days)."""
    if not days_str:
        return True
    try:
        return weekday in [int(d) for d in days_str.split(",") if d.strip()]
    except Exception:
        return True


async def _build_daily_goal(user: dict) -> int:
    w  = user.get("weight_kg") or 70
    h  = user.get("height_cm") or 170
    ag = user.get("age")       or 30
    bmr = 10 * w + 6.25 * h - 5 * ag + 5
    mults = {"sedentary": 1.2, "lightly_active": 1.375, "active": 1.55, "very_active": 1.725}
    return int(bmr * mults.get(user.get("activity_level", "sedentary"), 1.2))


# ---------------------------------------------------------------------------
# Main proactive message dispatcher (runs every 5 min)
# ---------------------------------------------------------------------------

async def check_proactive_messages():
    if _bot_app is None:
        return

    now     = datetime.now(ART)
    cur_min = now.hour * 60 + now.minute
    today_wd = now.weekday()  # 0=Mon … 6=Sun

    users = db.get_all_users()

    # Seed defaults for new users with no eating schedule
    existing_ids = {s["user_id"] for s in db.get_all_eating_schedules()}
    for user in users:
        if user["id"] not in existing_ids and user.get("onboarding_complete"):
            seed_default_schedules(user["id"])

    meal_schedules    = db.get_all_eating_schedules()
    workout_schedules = db.get_all_workout_schedules()

    for user in users:
        uid         = user["id"]
        telegram_id = user["telegram_id"]
        today_meals    = db.get_today_meals(telegram_id)
        today_workouts = db.get_today_workouts(telegram_id)
        daily_goal     = await _build_daily_goal(user)

        logged_meal_types    = {m["meal_type"]    for m in today_meals}
        logged_workout_types = {w["workout_type"] for w in today_workouts}

        # ── Meal triggers ───────────────────────────────────────────────
        user_meal_scheds = [s for s in meal_schedules if s["user_id"] == uid]
        for sched in user_meal_scheds:
            meal_type  = sched["meal_type"]
            meal_min   = _minutes(sched["avg_hour"], sched["avg_minute"])
            pre_min    = (meal_min - 30) % 1440
            follow_min = (meal_min + 45) % 1440

            # Pre-meal reminder (30 min before, meal not logged yet)
            if (meal_type not in logged_meal_types
                    and _near(cur_min, pre_min)
                    and not db.already_sent_followup_today(uid, "pre_meal", meal_type)):
                await _send_proactive(
                    user, telegram_id,
                    trigger="pre_meal",
                    trigger_info={"meal_type": meal_type},
                    ftype="pre_meal",
                    label=meal_type,
                    today_meals=today_meals,
                    today_workouts=today_workouts,
                    daily_goal=daily_goal,
                )

            # Meal follow-up (45 min after, still not logged)
            elif (meal_type not in logged_meal_types
                    and _near(cur_min, follow_min)
                    and not db.already_sent_followup_today(uid, "meal_followup", meal_type)):
                await _send_proactive(
                    user, telegram_id,
                    trigger="meal_followup",
                    trigger_info={"meal_type": meal_type},
                    ftype="meal_followup",
                    label=meal_type,
                    today_meals=today_meals,
                    today_workouts=today_workouts,
                    daily_goal=daily_goal,
                )

        # ── Workout triggers ─────────────────────────────────────────────
        user_wo_scheds = [s for s in workout_schedules if s["user_id"] == uid]
        for sched in user_wo_scheds:
            if not _day_matches(sched.get("days_of_week", ""), today_wd):
                continue

            workout_type = sched["workout_type"]
            wo_start_min = _minutes(sched["avg_hour"], sched["avg_minute"])
            avg_dur      = sched.get("avg_duration_min") or 60
            checkin_min  = (wo_start_min + avg_dur + 20) % 1440  # 20 min after usual end

            if (workout_type not in logged_workout_types
                    and _near(cur_min, checkin_min)
                    and not db.already_sent_followup_today(uid, "workout_checkin", workout_type)):
                await _send_proactive(
                    user, telegram_id,
                    trigger="workout_checkin",
                    trigger_info={"workout_type": workout_type},
                    ftype="workout_checkin",
                    label=workout_type,
                    today_meals=today_meals,
                    today_workouts=today_workouts,
                    daily_goal=daily_goal,
                )


async def _send_proactive(user, telegram_id, trigger, trigger_info,
                          ftype, label, today_meals, today_workouts, daily_goal):
    if not await _can_send_proactive(telegram_id):
        logger.info(f"[scheduler] Cooldown active for {telegram_id}, skipping {ftype}/{label}")
        return
    try:
        message = await ai.generate_proactive_message(
            user=user,
            trigger=trigger,
            trigger_info=trigger_info,
            today_meals=today_meals,
            today_workouts=today_workouts,
            daily_goal=daily_goal,
        )
        await _bot_app.bot.send_message(chat_id=telegram_id, text=message)
        db.add_followup(user["id"], message, ftype)
        db.update_last_proactive_sent(telegram_id)
        logger.info(f"[scheduler] Sent {ftype}/{label} to {telegram_id}")
    except Exception as e:
        logger.error(f"[scheduler] Error sending {ftype} to {telegram_id}: {e}")


# ---------------------------------------------------------------------------
# Daily summary at 21:00
# ---------------------------------------------------------------------------

async def check_reminders():
    """Send any pending user-requested reminders."""
    if _bot_app is None:
        return
    reminders = db.get_pending_reminders()
    for r in reminders:
        try:
            await _bot_app.bot.send_message(
                chat_id=r["telegram_id"],
                text=f"\u23f0 {r['message']}"
            )
            db.mark_reminder_sent(r["id"])
            logger.info(f"[scheduler] Sent reminder {r['id']} to {r['telegram_id']}")
        except Exception as e:
            logger.error(f"[scheduler] Error sending reminder {r['id']}: {e}")


async def check_meal_absence():
    """Nudge users who have not logged a meal in 5+ hours during daytime."""
    if _bot_app is None:
        return
    import pytz
    from datetime import datetime, timedelta
    tz = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(tz)
    if not (10 <= now.hour < 22):
        return
    users = db.get_all_users()
    for user in users:
        if not user.get("onboarding_complete"):
            continue
        tid = user["telegram_id"]
        last = db.get_last_meal_time(tid)
        if last is None:
            continue
        try:
            from datetime import datetime as dt
            if isinstance(last, str):
                last_dt = dt.fromisoformat(last.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = tz.localize(last_dt)
            else:
                last_dt = last
                if last_dt.tzinfo is None:
                    last_dt = tz.localize(last_dt)
            hours_since = (now - last_dt.astimezone(tz)).total_seconds() / 3600
            if hours_since >= 5:
                uid = user.get("id", 0)
                if not db.already_sent_followup_today(uid, "absence_nudge"):
                    if not await _can_send_proactive(tid):
                        logger.info(f"[scheduler] Cooldown active for {tid}, skipping absence nudge")
                        continue
                    await _bot_app.bot.send_message(
                        chat_id=tid,
                        text=f"\u23f0 Pasaron {int(hours_since)}hs desde tu ultima comida registrada. Ya comiste algo? No te olvides de registrarlo."
                    )
                    db.update_last_proactive_sent(tid)
                    db.add_followup(uid, f"absence_nudge_{now.hour}", "absence_nudge")
        except Exception as e:
            logger.error(f"[scheduler] absence check error for {tid}: {e}")


async def check_training_reminders():
    """Send pre-workout nutrition tip 30 min before scheduled training."""
    if _bot_app is None:
        return
    import pytz
    from datetime import datetime
    tz = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(tz)
    today_weekday = now.weekday()  # 0=Monday
    cur_min = now.hour * 60 + now.minute

    users = db.get_all_users()
    for user in users:
        if not user.get("onboarding_complete"):
            continue
        training_schedule = user.get("training_schedule")
        if not training_schedule:
            continue
        tid = user["telegram_id"]
        uid = user.get("id", 0)

        parsed = _parse_training_schedule(training_schedule)
        for slot in parsed:
            if slot["weekday"] != today_weekday:
                continue

            # Send reminder 30 min before training
            training_min = slot["hour"] * 60 + slot["minute"]
            reminder_min = training_min - 30
            if reminder_min < 0:
                reminder_min += 1440

            if not _near(cur_min, reminder_min, window=3):
                continue

            # Check dedup
            fkey = f"preworkout_{now.strftime('%Y-%m-%d')}_{slot['weekday']}_{slot['hour']}"
            if db.already_sent_followup_today(uid, fkey):
                continue

            db.add_followup(uid, fkey, fkey)

            if not await _can_send_proactive(tid):
                logger.info(f"[scheduler] Cooldown active for {tid}, skipping pre-workout reminder")
                continue

            try:
                goal = user.get("goal", "maintain")
                tip = await ai._ask([{"role": "user", "content":
                    f"Dales a {user.get('name', 'vos')} un tip nutricional corto (2 l\u00edneas m\u00e1x) para antes de entrenar. "
                    f"Su objetivo es {goal}. Algo concreto: qu\u00e9 comer antes del gym. "
                    f"Tono: semiformal argentino, directo. Empez\u00e1 con '\u23f0 En 30 min ten\u00e9s el gym.'"}])
                await _bot_app.bot.send_message(chat_id=tid, text=tip)
                db.update_last_proactive_sent(tid)
                logger.info(f"[scheduler] Sent pre-workout reminder to {tid}")
            except Exception as e:
                logger.error(f"[scheduler] Pre-workout reminder error for {tid}: {e}")


async def send_daily_summaries():
    if _bot_app is None:
        return
    users = db.get_all_users()
    for user in users:
        telegram_id = user["telegram_id"]
        user_id     = user["id"]
        meals = db.get_today_meals(telegram_id)
        if not meals:
            continue
        if db.already_sent_followup_today(user_id, "summary"):
            continue
        try:
            await _send_summary_to_user(user, meals)
            db.add_followup(user_id, "summary_chart", "summary")
            logger.info(f"[scheduler] Sent daily summary to {telegram_id}")
        except Exception as e:
            logger.error(f"[scheduler] Error sending daily summary to {telegram_id}: {e}")


async def _send_summary_to_user(user: dict, meals: list):
    telegram_id = user["telegram_id"]
    daily_goal  = charts.estimate_daily_calories(user)
    total_cal   = sum(m.get("calories_est", 0) or 0 for m in meals)
    workouts    = db.get_today_workouts(telegram_id)

    try:
        png_bytes = await charts.generate_daily_summary_chart(user, meals)
        caption   = await ai.generate_chart_caption(user, meals, total_cal, daily_goal)
        # Add workout summary to caption if any
        if workouts:
            burned = sum(w.get("calories_burned", 0) or 0 for w in workouts)
            caption += f"\n🏃 Entrenamiento: {burned} kcal quemadas hoy."
        await _bot_app.bot.send_photo(
            chat_id=telegram_id,
            photo=BytesIO(png_bytes),
            caption=caption,
        )
    except Exception as chart_err:
        logger.warning(f"Chart failed for {telegram_id}: {chart_err} — falling back to text")
        message = await ai.generate_daily_summary(user, meals)
        if message:
            await _bot_app.bot.send_message(chat_id=telegram_id, text=message)

# ---------------------------------------------------------------------------
# Proactive meal check-in jobs
# ---------------------------------------------------------------------------

async def send_meal_checkin(meal_type: str):
    """Send proactive meal check-in to all active users."""
    if _bot_app is None:
        return
    import pytz
    from datetime import datetime
    tz = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(tz)

    users = db.get_all_users()
    for user in users:
        if not user.get("onboarding_complete"):
            continue
        tid = user["telegram_id"]
        uid = user.get("id", 0)

        # Skip if user was active recently (already in conversation)
        last_seen = db.get_last_seen(tid)
        if last_seen:
            try:
                ls_dt = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
                if ls_dt.tzinfo is None:
                    ls_dt = tz.localize(ls_dt)
                if (now - ls_dt.astimezone(tz)).total_seconds() < 900:
                    continue  # user was active in last 15 min, skip checkin
            except Exception:
                pass

        # Don't send if user already logged THIS meal type today
        today_meals = db.get_today_meals(tid)
        if any(m.get("meal_type") == meal_type for m in today_meals):
            continue  # already logged this meal type today, skip

        # Check daily limit - don't spam
        followup_key = f"{meal_type}_checkin_{now.strftime('%Y-%m-%d')}"
        if db.already_sent_followup_today(uid, followup_key):
            continue

        # Mark as sent BEFORE sending to prevent duplicates on retry
        db.add_followup(uid, followup_key, followup_key)

        if not await _can_send_proactive(tid):
            logger.info(f"[scheduler] Cooldown active for {tid}, skipping {meal_type} checkin")
            continue

        try:
            memories = db.get_memories(tid, limit=10)
            msg = await ai.generate_checkin_message(user, meal_type, memories)
            await _bot_app.bot.send_message(chat_id=tid, text=msg)
            db.update_last_proactive_sent(tid)
            logger.info(f"[scheduler] Sent {meal_type} checkin to {tid}")
        except Exception as e:
            logger.error(f"[scheduler] {meal_type} checkin error for {tid}: {e}")


async def send_inactivity_checkin():
    """Check for users inactive 3+ hours during daytime and send a check-in."""
    if _bot_app is None:
        return
    import pytz
    from datetime import datetime
    tz = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(tz)

    # Only between 10:00 and 22:00
    if not (10 <= now.hour < 22):
        return

    users = db.get_all_users()
    for user in users:
        if not user.get("onboarding_complete"):
            continue
        tid = user["telegram_id"]
        uid = user.get("id", 0)

        last_seen = db.get_last_seen(tid)
        if last_seen is None:
            continue

        try:
            ls_dt = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
            if ls_dt.tzinfo is None:
                ls_dt = tz.localize(ls_dt)
            hours_inactive = (now - ls_dt.astimezone(tz)).total_seconds() / 3600

            if hours_inactive < 3:
                continue

            # Max 1 inactivity message per 4-hour window
            followup_key = f"inactivity_{now.strftime('%Y%m%d')}_{now.hour // 4}"
            if db.already_sent_followup_today(uid, followup_key):
                continue

            # Mark as sent BEFORE sending to prevent duplicates on retry
            db.add_followup(uid, followup_key, followup_key)

            if not await _can_send_proactive(tid):
                logger.info(f"[scheduler] Cooldown active for {tid}, skipping inactivity checkin")
                continue

            memories = db.get_memories(tid, limit=10)
            # Pick the right trigger based on current hour
            if 6 <= now.hour < 12:
                inactivity_trigger = "breakfast"
            elif 12 <= now.hour < 16:
                inactivity_trigger = "lunch"
            elif 16 <= now.hour < 20:
                inactivity_trigger = "afternoon"
            else:
                inactivity_trigger = "dinner"
            msg = await ai.generate_checkin_message(user, inactivity_trigger, memories)
            await _bot_app.bot.send_message(chat_id=tid, text=msg)
            db.update_last_proactive_sent(tid)
            logger.info(f"[scheduler] Sent inactivity checkin to {tid} ({hours_inactive:.1f}h inactive)")
        except Exception as e:
            logger.error(f"[scheduler] inactivity checkin error for {tid}: {e}")
