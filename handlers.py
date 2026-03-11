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
    total_prot = sum(float(m.get("proteins_g", 0) or 0) for m in meals)
    daily_goal = charts_module.estimate_daily_calories(user)
    pct = round(total_cal / daily_goal * 100) if daily_goal else 0
    remaining = max(0, daily_goal - total_cal)

    meal_type_names = {"breakfast": "Desayuno", "lunch": "Almuerzo", "dinner": "Cena", "snack": "Merienda"}
    lines = [f"📊 *{user['name']} — hoy*\n"]
    for m in meals:
        try:
            t = datetime.fromisoformat(m["eaten_at"]).strftime("%H:%M")
        except Exception:
            t = "?"
        cal = m.get("calories_est", 0) or 0
        tipo = meal_type_names.get(m.get("meal_type", ""), "Comida")
        desc = (m.get("description", "") or "")[:35]
        lines.append(f"• {t} {tipo}: {desc} (~{cal} kcal)")

    # Progress bar
    filled = min(10, pct // 10)
    bar = "█" * filled + "░" * (10 - filled)
    lines.append(f"\n🔥 *{total_cal} / {daily_goal} kcal* [{bar}] {pct}%")
    lines.append(f"🥩 Proteína acumulada: *{total_prot:.0f}g*")
    if remaining > 0:
        lines.append(f"📉 Te quedan ~{remaining} kcal para hoy")
    else:
        lines.append("✅ ¡Ya alcanzaste tu meta calórica de hoy!")

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

    # If we're waiting for clarification on a vague meal
    pending = context.user_data.get("pending_meal_text")
    if pending:
        # Let user cancel
        if text.lower() in ("no", "cancelar", "cancel", "nada", "olvidate", "olvida"):
            context.user_data.pop("pending_meal_text", None)
            await update.message.reply_text("Ok, no registré nada 👌")
            return
        context.user_data.pop("pending_meal_text", None)
        combined = f"{pending} — {text}"
        await _log_meal_text(update, context, user, combined)
        return

    # Check if nutrition/food related at all
    is_nutrition = await ai.classify_intent(text)
    if not is_nutrition:
        await update.message.reply_text(
            "Solo puedo ayudarte con nutrición y alimentación 🥗\n"
            "Contame qué comiste o haceme una consulta sobre tu dieta!"
        )
        return

    # Check if it's a food log or a nutrition question
    is_log = await ai.is_food_log(text)
    if not is_log:
        # It's a nutrition question — answer directly
        response = await ai.answer_nutrition_question(text, user)
        await update.message.reply_text(response)
        return

    # Check if description is too vague
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
    cost_line = f"\n\n_💰 ${cost:.5f} USD_"
    try:
        await update.message.reply_text(response + cost_line, parse_mode="Markdown")
    except Exception:
        # Fallback sin markdown si hay caracteres especiales
        await update.message.reply_text(response.replace("*", "").replace("_", "") + f"\n\n💰 ${cost:.5f} USD")


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🥗 *NutriBot — Comandos disponibles*\n\n"
        "📝 *Registrar comida:* mandá lo que comiste en texto o foto\n"
        "   _Ej: 'comí 200g de pollo con ensalada'_\n\n"
        "/plan — Ver tu plan de alimentación personalizado\n"
        "/stats — Ver estadísticas del día\n"
        "/resumen — Gráfico nutricional del día\n"
        "/perfil — Ver tu perfil actual\n"
        "/borrar — Eliminar la última comida registrada\n"
        "/reset — Reiniciar tu perfil desde cero\n"
        "/ayuda — Mostrar este menú",
        parse_mode="Markdown"
    )


async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Todavía no configuraste tu perfil. Usá /start para empezar.")
        return

    goal_map = {"lose_weight": "Bajar de peso", "gain_muscle": "Ganar músculo", "maintain": "Mantener peso", "improve_health": "Mejorar salud"}
    activity_map = {"sedentary": "Sedentario", "light": "Actividad leve", "moderate": "Moderado", "active": "Activo", "very_active": "Muy activo"}

    await update.message.reply_text(
        f"👤 *Tu perfil*\n\n"
        f"Nombre: {user.get('name', '?')}\n"
        f"Edad: {user.get('age', '?')} años\n"
        f"Peso: {user.get('weight_kg', '?')} kg\n"
        f"Altura: {user.get('height_cm', '?')} cm\n"
        f"Objetivo: {goal_map.get(user.get('goal', ''), user.get('goal', '?'))}\n"
        f"Actividad: {activity_map.get(user.get('activity_level', ''), user.get('activity_level', '?'))}\n\n"
        "_Para modificar tu perfil usá /reset_",
        parse_mode="Markdown"
    )


async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero configurá tu perfil con /start.")
        return
    deleted = db.delete_last_meal(telegram_id)
    if deleted:
        await update.message.reply_text(f"🗑 Eliminé tu última comida registrada: _{deleted}_", parse_mode="Markdown")
    else:
        await update.message.reply_text("No encontré comidas registradas para eliminar.")
