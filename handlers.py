import os
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import ai
import db
import charts as charts_module
import scheduler as sched_module

logger = logging.getLogger(__name__)


def _onboarding_url(telegram_id: int) -> str:
    token = db.create_onboarding_token(telegram_id)
    base_url = os.environ.get("WEB_BASE_URL", "http://localhost:8080")
    return f"{base_url}/onboarding/{token}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    db.upsert_user(telegram_id, onboarding_complete=0)
    context.user_data.clear()
    url = _onboarding_url(telegram_id)
    await update.message.reply_text(
        "¡Hola! 👋 Soy tu coach de nutrición personal.\n\n"
        "Para empezar, completá tu perfil en este link — solo te lleva un minuto:\n\n"
        f"{url}"
    )


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero necesito conocerte un poco 😊 Usá /start para empezar.")
        return
    await update.message.reply_text("Un momento, armando tu plan... 🥗")
    plan = await ai.generate_meal_plan(user)
    await update.message.reply_text(plan)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero necesito conocerte 😊 Usá /start.")
        return

    meals = db.get_today_meals(telegram_id)
    if not meals:
        await update.message.reply_text("Todavía no registraste ninguna comida hoy 🍽️ ¡Mandame una foto o describí lo que comés!")
        return

    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)
    lines = [f"📊 *Resumen de hoy, {user['name']}:*\n"]
    for m in meals:
        t = datetime.fromisoformat(m["eaten_at"]).strftime("%H:%M")
        cal = m.get("calories_est", 0) or 0
        lines.append(f"• {t} — {m.get('meal_type', 'comida')}: {m.get('description', '')[:40]} (~{cal} kcal)")
    lines.append(f"\n🔥 *Total estimado: {total_cal} kcal*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    db.upsert_user(telegram_id, onboarding_complete=0, name=None, age=None,
                   weight_kg=None, height_cm=None, goal=None, activity_level=None)
    context.user_data.clear()
    url = _onboarding_url(telegram_id)
    await update.message.reply_text(
        f"Perfecto, empezamos de cero 🔄\n\nCompletá tu nuevo perfil acá:\n\n{url}"
    )


async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero necesito conocerte 😊 Usá /start.")
        return

    meals = db.get_today_meals(telegram_id)
    if not meals:
        await update.message.reply_text("Todavía no registraste ninguna comida hoy 🍽️ ¡Mandame una foto o describí qué comiste!")
        return

    await update.message.reply_text("Generando tu resumen del día... 📊")

    daily_goal = charts_module.estimate_daily_calories(user)
    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)

    try:
        png_bytes = await charts_module.generate_daily_summary_chart(user, meals)
        caption = await ai.generate_chart_caption(user, meals, total_cal, daily_goal)
        await update.message.reply_photo(photo=png_bytes, caption=caption)
    except Exception as e:
        logger.error(f"[resumen] Chart error for {telegram_id}: {e}")
        message = await ai.generate_daily_summary(user, meals)
        if message:
            await update.message.reply_text(message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text(
            "Hola 👋 Usá /start para configurar tu perfil y empezar."
        )
        return

    # If we're waiting for clarification on a vague meal, combine and log
    pending = context.user_data.get("pending_meal_text")
    if pending:
        context.user_data.pop("pending_meal_text", None)
        combined = f"{pending} — {text}"
        await _log_meal_text(update, context, user, combined)
        return

    is_food = await ai.classify_intent(text)
    if not is_food:
        await update.message.reply_text(
            "Solo puedo ayudarte con el registro de tus comidas 🍽️\n"
            "Contame qué comiste o mandame una foto!"
        )
        return

    # Check if description is too vague (e.g. "comí" with no food specified)
    follow_up_question = await ai.check_meal_vague(text)
    if follow_up_question:
        context.user_data["pending_meal_text"] = text
        await update.message.reply_text(follow_up_question)
        return

    await _log_meal_text(update, context, user, text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero configurá tu perfil con /start 😊")
        return

    await update.message.reply_text("Analizando tu foto... 🔍")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    os.makedirs("photos", exist_ok=True)
    photo_path = f"photos/{telegram_id}_{photo.file_id}.jpg"
    await file.download_to_drive(photo_path)

    caption = update.message.caption or ""
    analysis = await ai.analyze_meal_photo(photo_path, user)

    await _save_and_reply_meal(update, user, analysis, caption or analysis.get("detected", ""), photo_path)


async def _log_meal_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user: dict, text: str):
    await update.message.reply_text("Registrando tu comida... 🍽️")
    ai.reset_turn_cost()
    analysis = await ai.analyze_meal_text(text, user)
    await _save_and_reply_meal(update, user, analysis, text, None)


async def _save_and_reply_meal(update: Update, user: dict, analysis: dict, description: str, photo_path):
    telegram_id = user["telegram_id"]
    user_id = user["id"]
    meal_type = analysis.get("meal_type", "snack")
    calories = analysis.get("calories", 0)

    try:
        calories = int(calories)
    except (ValueError, TypeError):
        calories = 0

    db.add_meal(
        user_id=user_id,
        telegram_id=telegram_id,
        description=description[:500],
        photo_path=photo_path or "",
        calories_est=calories,
        meal_type=meal_type,
        claude_analysis=analysis.get("full_response", ""),
        proteins_g=analysis.get("proteins_g", 0),
        carbs_g=analysis.get("carbs_g", 0),
        fats_g=analysis.get("fats_g", 0),
    )

    sched_module.update_eating_schedule(user_id, meal_type)

    response = analysis.get("full_response", "")
    if not response:
        detected = analysis.get("detected", "tu comida")
        tip = analysis.get("tip", "")
        aligned = analysis.get("aligned", "")
        response = (
            f"✅ Registré: *{detected}* (~{calories} kcal)\n"
            f"{'🎯 Va bien con tu objetivo!' if aligned == 'sí' else '💡 ' + tip if tip else ''}"
        )

    cost = ai.get_turn_cost()
    response += f"\n\n_💰 ${cost:.5f} USD_"
    await update.message.reply_text(response, parse_mode="Markdown")
