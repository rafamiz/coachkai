import asyncio
import logging
from datetime import datetime, timedelta
from io import BytesIO

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
import ai
import charts

logger = logging.getLogger(__name__)

_bot_app = None
_scheduler = None

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]


def start_scheduler(app):
    global _bot_app, _scheduler
    _bot_app = app
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(check_and_send_followups, "interval", minutes=5, id="followup_check")
    _scheduler.add_job(update_all_schedules, "interval", hours=1, id="schedule_update")
    # 21:00 ART = 00:00 UTC (UTC-3)
    _scheduler.add_job(send_daily_summaries, "cron", hour=0, minute=0, id="daily_summary")
    _scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)


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
    avg_hour = int(avg)
    avg_minute = (avg - avg_hour) * 60

    confidence = min(100, len(hours) * 10)
    db.upsert_eating_schedule(user_id, meal_type, avg_hour, avg_minute, confidence, len(hours))


def update_all_schedules():
    users = db.get_all_users()
    for user in users:
        for meal_type in MEAL_TYPES:
            update_eating_schedule(user["id"], meal_type)


async def check_and_send_followups():
    if _bot_app is None:
        return

    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    schedules = db.get_all_eating_schedules()

    for sched in schedules:
        user_id = sched["user_id"]
        telegram_id = sched["telegram_id"]
        meal_type = sched["meal_type"]

        meal_time_minutes = int(sched["avg_hour"]) * 60 + int(sched["avg_minute"])
        reminder_minutes = meal_time_minutes - 30

        if reminder_minutes < 0:
            reminder_minutes += 1440

        diff = abs(current_minutes - reminder_minutes)
        if diff > 3 and diff < (1440 - 3):
            continue

        if db.already_sent_followup_today(user_id, "reminder", meal_type):
            continue

        user = db.get_user(telegram_id)
        if not user:
            continue

        try:
            message = await ai.generate_followup_message(user, meal_type, "reminder")
            await _bot_app.bot.send_message(chat_id=telegram_id, text=message)
            db.add_followup(user_id, message, "reminder")
            logger.info(f"Sent reminder to {telegram_id} for {meal_type}")
        except Exception as e:
            logger.error(f"Error sending followup to {telegram_id}: {e}")


async def send_daily_summaries():
    if _bot_app is None:
        return

    users = db.get_all_users()
    for user in users:
        telegram_id = user["telegram_id"]
        user_id = user["id"]
        meals = db.get_today_meals(telegram_id)
        if not meals:
            continue

        if db.already_sent_followup_today(user_id, "summary"):
            continue

        try:
            await _send_summary_to_user(user, meals)
            db.add_followup(user_id, "summary_chart", "summary")
            logger.info(f"Sent daily summary to {telegram_id}")
        except Exception as e:
            logger.error(f"Error sending daily summary to {telegram_id}: {e}")


async def _send_summary_to_user(user: dict, meals: list):
    """Send chart image + text caption to one user. Used by scheduler and /resumen command."""
    telegram_id = user["telegram_id"]
    daily_goal = charts.estimate_daily_calories(user)
    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)

    try:
        png_bytes = await charts.generate_daily_summary_chart(user, meals)
        caption = await ai.generate_chart_caption(user, meals, total_cal, daily_goal)
        await _bot_app.bot.send_photo(
            chat_id=telegram_id,
            photo=BytesIO(png_bytes),
            caption=caption,
        )
    except Exception as chart_err:
        logger.warning(f"Chart generation failed for {telegram_id}: {chart_err} — falling back to text")
        message = await ai.generate_daily_summary(user, meals)
        if message:
            await _bot_app.bot.send_message(chat_id=telegram_id, text=message)


def get_bot_app():
    return _bot_app
