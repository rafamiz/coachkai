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
                    await _bot_app.bot.send_message(
                        chat_id=tid,
                        text=f"\u23f0 Pasaron {int(hours_since)}hs desde tu ultima comida registrada. Ya comiste algo? No te olvides de registrarlo."
                    )
                    db.add_followup(uid, f"absence_nudge_{now.hour}", "absence_nudge")
        except Exception as e:
            logger.error(f"[scheduler] absence check error for {tid}: {e}")


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
