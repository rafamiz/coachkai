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

    await update.message.reply_text("ðŸŒ¿ *Bienvenido a Coach Kai*\n_Tu coach personal de nutriciÃ³n_", parse_mode="Markdown")
    await update.message.chat.send_action("typing")

    result = await ai.intake_turn([], "Hi, I just started using the app.")
    reply = result.get("reply", "")

    intake_history = [
        {"role": "user", "content": "Hi, I just started using the app."},
        {"role": "assistant", "content": reply},
    ]
    context.user_data["intake_history"] = intake_history
    db.save_onboarding_history(telegram_id, intake_history)

    await update.message.reply_text(reply)


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero necesito conocerte un poco ðŸ˜Š UsÃ¡ /start para empezar.")
        return
    await update.message.reply_text("Armando tu plan personalizado... ðŸ¥— (en unos segundos te mando el PDF)")
    plan = await ai.generate_meal_plan(user)
    await update.message.reply_text(plan)
    # Generate and send PDF
    try:
        import pdf_generator
        pdf_bytes = pdf_generator.generate_plan_pdf(user, plan)
        from io import BytesIO
        await update.message.reply_document(
            document=BytesIO(pdf_bytes),
            filename=f"plan_coachkai_{user.get('name', 'usuario').lower().replace(' ', '_')}.pdf",
            caption="ðŸ“„ Tu plan de alimentaciÃ³n personalizado â€” Coach Kai"
        )
    except Exception as e:
        logger.error(f"PDF generation error: {e}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero necesito conocerte ðŸ˜Š UsÃ¡ /start.")
        return

    meals = db.get_today_meals(telegram_id)
    if not meals:
        await update.message.reply_text("TodavÃ­a no registraste ninguna comida hoy ðŸ½ï¸ Â¡Mandame una foto o describÃ­ lo que comÃ©s!")
        return

    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)
    total_prot = sum(float(m.get("proteins_g", 0) or 0) for m in meals)
    daily_goal = charts_module.estimate_daily_calories(user)
    pct = round(total_cal / daily_goal * 100) if daily_goal else 0
    remaining = max(0, daily_goal - total_cal)

    meal_type_names = {"breakfast": "Desayuno", "lunch": "Almuerzo", "dinner": "Cena", "snack": "Merienda"}
    lines = [f"ðŸ“Š *{user['name']} â€” hoy*\n"]
    for m in meals:
        try:
            t = datetime.fromisoformat(m["eaten_at"]).strftime("%H:%M")
        except Exception:
            t = "?"
        cal = m.get("calories_est", 0) or 0
        tipo = meal_type_names.get(m.get("meal_type", ""), "Comida")
        desc = (m.get("description", "") or "")[:35]
        lines.append(f"â€¢ {t} {tipo}: {desc} (~{cal} kcal)")

    # Progress bar
    filled = min(10, pct // 10)
    bar = "â–ˆ" * filled + "â–‘" * (10 - filled)
    lines.append(f"\nðŸ”¥ *{total_cal} / {daily_goal} kcal* [{bar}] {pct}%")
    lines.append(f"ðŸ¥© ProteÃ­na acumulada: *{total_prot:.0f}g*")
    if remaining > 0:
        lines.append(f"ðŸ“‰ Te quedan ~{remaining} kcal para hoy")
    else:
        lines.append("âœ… Â¡Ya alcanzaste tu meta calÃ³rica de hoy!")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    db.upsert_user(telegram_id, onboarding_complete=0, name=None, age=None,
                   weight_kg=None, height_cm=None, goal=None, activity_level=None,
                   profile_text=None, onboarding_history=None)
    context.user_data.clear()
    await cmd_start(update, context)


async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero necesito conocerte ðŸ˜Š UsÃ¡ /start.")
        return

    meals = db.get_today_meals(telegram_id)
    if not meals:
        await update.message.reply_text("TodavÃ­a no registraste ninguna comida hoy ðŸ½ï¸ Â¡Mandame una foto o describÃ­ quÃ© comiste!")
        return

    await update.message.reply_text("Generando tu resumen del dÃ­a... ðŸ“Š")

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


async def handle_intake_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    # Load history from memory or DB
    intake_history = context.user_data.get("intake_history")
    if intake_history is None:
        intake_history = db.get_onboarding_history(telegram_id)
        if not intake_history:
            await cmd_start(update, context)
            return
        context.user_data["intake_history"] = intake_history

    await update.message.chat.send_action("typing")
    result = await ai.intake_turn(intake_history, text)

    intake_history = intake_history + [{"role": "user", "content": text}]
    if result.get("reply"):
        intake_history = intake_history + [{"role": "assistant", "content": result["reply"]}]

    context.user_data["intake_history"] = intake_history
    db.save_onboarding_history(telegram_id, intake_history)

    if result["done"]:
        profile = result["profile"]
        db.upsert_user(
            telegram_id,
            name=profile["name"],
            age=profile["age"],
            weight_kg=profile["weight_kg"],
            height_cm=profile["height_cm"],
            goal=profile["goal"],
            activity_level=profile["activity_level"],
            onboarding_complete=1,
            onboarding_history=None,
        )
        db.save_profile_text(telegram_id, profile["identity_markdown"])

        context.user_data.pop("intake_history", None)
        context.user_data["history"] = []

        if result.get("reply"):
            await update.message.reply_text(result["reply"])

        full_user = db.get_user(telegram_id)
        welcome = await ai.onboarding_welcome(profile["name"])
        await update.message.reply_text(welcome)

        plan = await ai.generate_meal_plan(full_user)
        await update.message.reply_text(plan)
        try:
            import pdf_generator
            from io import BytesIO
            pdf_bytes = pdf_generator.generate_plan_pdf(full_user, plan)
            await update.message.reply_document(
                document=BytesIO(pdf_bytes),
                filename=f"plan_coachkai_{profile['name'].lower().replace(' ', '_')}.pdf",
                caption="ðŸ“„ Tu plan de alimentaciÃ³n personalizado â€” Coach Kai"
            )
        except Exception as e:
            logger.error(f"PDF error post-intake: {e}")
    else:
        await update.message.reply_text(result["reply"])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await handle_intake_message(update, context)
        return

    history = context.user_data.get("history", [])

    await update.message.chat.send_action("typing")
    ai.reset_turn_cost()
    result = await ai.process_message(text, user, history)

    history = history + [{"role": "user", "content": text}]

    if result["type"] == "meal":
        if result.get("reply"):
            history = history + [{"role": "assistant", "content": result["reply"]}]
        context.user_data["history"] = history[-50:]
        await _save_and_reply_meal(update, user, result["meal"])

    elif result["type"] == "workout":
        if result.get("reply"):
            history = history + [{"role": "assistant", "content": result["reply"]}]
        context.user_data["history"] = history[-50:]
        await _save_and_reply_workout(update, user, result["workout"])

    elif result["type"] == "identity_update":
        upd = result["update"]
        kwargs = {"profile_text": upd["identity_markdown"]}
        if upd.get("weight_kg"):      kwargs["weight_kg"]      = upd["weight_kg"]
        if upd.get("goal"):           kwargs["goal"]           = upd["goal"]
        if upd.get("activity_level"): kwargs["activity_level"] = upd["activity_level"]
        db.upsert_user(telegram_id, **kwargs)
        db.save_profile_text(telegram_id, upd["identity_markdown"])
        reply = result.get("reply") or "âœ… ActualicÃ© tu perfil con la nueva info."
        history = history + [{"role": "assistant", "content": reply}]
        context.user_data["history"] = history[-50:]
        await update.message.reply_text(reply)

    else:
        response = result["content"]
        history = history + [{"role": "assistant", "content": response}]
        context.user_data["history"] = history[-50:]
        await update.message.reply_text(response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero terminÃ¡ de contarme sobre vos ðŸ˜Š Â¡Ya casi!")
        return

    await update.message.reply_text("Analizando tu foto... ðŸ”")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    os.makedirs("photos", exist_ok=True)
    photo_path = f"photos/{telegram_id}_{photo.file_id}.jpg"
    await file.download_to_drive(photo_path)

    caption = update.message.caption or ""
    history = context.user_data.get("history", [])

    ai.reset_turn_cost()
    result = await ai.process_message(
        text=caption or "Log this meal from the photo.",
        user=user,
        history=history,
        photo_path=photo_path,
    )

    history = history + [{"role": "user", "content": "[foto de comida]" + (f": {caption}" if caption else "")}]

    if result["type"] == "meal":
        meal = result["meal"]
        if result.get("reply"):
            history = history + [{"role": "assistant", "content": result["reply"]}]
        context.user_data["history"] = history[-50:]
        await _save_and_reply_meal(update, user, meal, photo_path=photo_path)
    else:
        response = result["content"]
        history = history + [{"role": "assistant", "content": response}]
        context.user_data["history"] = history[-50:]
        await update.message.reply_text(response)


async def _save_and_reply_meal(update: Update, user: dict, meal: dict, photo_path: str = None):
    """Save a meal from a log_meal tool call and reply with a formatted summary."""
    telegram_id = user["telegram_id"]
    user_id = user["id"]

    detected  = meal.get("detected_food", "tu comida")
    meal_type = meal.get("meal_type", "snack")
    tip       = meal.get("tip", "")
    aligned   = meal.get("aligned_with_goal", "partial")

    try:
        calories = int(meal.get("calories", 0))
    except (ValueError, TypeError):
        calories = 0
    proteins_g = float(meal.get("proteins_g", 0) or 0)
    carbs_g    = float(meal.get("carbs_g",    0) or 0)
    fats_g     = float(meal.get("fats_g",     0) or 0)

    # Try Open Food Facts to improve accuracy
    source_note = "âš ï¸ _estimaciÃ³n Kai_"
    try:
        import nutrition as nutr
        off = await nutr.get_nutrition_for_meal(detected, "")
        if off:
            calories   = off["calories"]
            proteins_g = off["proteins_g"]
            carbs_g    = off["carbs_g"]
            fats_g     = off["fats_g"]
            detected   = off["food_name"]
            source_note = "ðŸ“Š _Open Food Facts_"
    except Exception:
        pass

    db.add_meal(
        user_id=user_id,
        telegram_id=telegram_id,
        description=detected[:500],
        photo_path=photo_path or "",
        calories_est=calories,
        meal_type=meal_type,
        claude_analysis=detected,
        proteins_g=proteins_g,
        carbs_g=carbs_g,
        fats_g=fats_g,
    )
    sched_module.update_eating_schedule(user_id, meal_type)

    # Format reply
    aligned_icon = {"yes": "ðŸŽ¯", "partial": "ðŸ‘", "no": "âš ï¸"}.get(aligned, "ðŸ‘")
    response = (
        f"âœ… *{detected}* Â· ~{calories} kcal\n"
        f"ðŸ¥© {proteins_g:.0f}g proteÃ­na Â· ðŸŒ¾ {carbs_g:.0f}g carbos Â· ðŸ«’ {fats_g:.0f}g grasa\n"
        f"{source_note}"
    )
    if tip:
        response += f"\n{aligned_icon} {tip}"

    cost = ai.get_turn_cost()
    cost_line = f"\n\n_ðŸ’° ${cost:.5f} USD_"
    try:
        await update.message.reply_text(response + cost_line, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(response.replace("*", "").replace("_", "") + f"\n\nðŸ’° ${cost:.5f} USD")


async def _save_and_reply_workout(update: Update, user: dict, workout: dict):
    """Save a workout from a log_workout tool call and reply with a formatted summary."""
    telegram_id = user["telegram_id"]
    user_id     = user["id"]

    description    = workout.get("description", "entrenamiento")
    workout_type   = workout.get("workout_type", "other")
    intensity      = workout.get("intensity", "moderate")
    notes          = workout.get("notes", "")
    distance_km    = workout.get("distance_km")

    try:
        duration_min   = int(workout.get("duration_min", 0))
        calories_burned = int(workout.get("calories_burned", 0))
    except (ValueError, TypeError):
        duration_min, calories_burned = 0, 0

    db.add_workout(
        user_id=user_id,
        telegram_id=telegram_id,
        workout_type=workout_type,
        description=description[:500],
        duration_min=duration_min,
        calories_burned=calories_burned,
        intensity=intensity,
        distance_km=distance_km,
        notes=notes,
    )
    sched_module.update_workout_schedule(user_id, workout_type)

    intensity_icons = {"low": "ðŸš¶", "moderate": "ðŸƒ", "high": "ðŸ”¥", "very_high": "ðŸ’¥"}
    icon = intensity_icons.get(intensity, "ðŸƒ")
    dist_str = f" Â· {distance_km:.1f} km" if distance_km else ""
    response = (
        f"{icon} *{description}*\n"
        f"â± {duration_min} min{dist_str} Â· ðŸ”¥ ~{calories_burned} kcal quemadas"
    )
    if notes:
        response += f"\nðŸ“ {notes}"

    cost = ai.get_turn_cost()
    cost_line = f"\n\n_ðŸ’° ${cost:.5f} USD_"
    try:
        await update.message.reply_text(response + cost_line, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(response.replace("*", "").replace("_", "") + f"\n\nðŸ’° ${cost:.5f} USD")


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ðŸ¥— *Coach Kai â€” Comandos disponibles*\n\n"
        "ðŸ“ *Registrar comida:* mandÃ¡ lo que comiste en texto o foto\n"
        "   _Ej: 'comÃ­ 200g de pollo con ensalada'_\n\n"
        "/plan â€” Ver tu plan de alimentaciÃ³n personalizado\n"
        "/stats â€” Ver estadÃ­sticas del dÃ­a\n"
        "/resumen â€” GrÃ¡fico nutricional del dÃ­a\n"
        "/perfil â€” Ver tu perfil actual\n"
        "/borrar â€” Eliminar la Ãºltima comida registrada\n"
        "/reset â€” Reiniciar tu perfil desde cero\n"
        "/ayuda â€” Mostrar este menÃº",
        parse_mode="Markdown"
    )


async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Todav\u00eda no configuraste tu perfil. Us\u00e1 /start para empezar.")
        return

    goal_map = {"lose_weight": "Bajar de peso", "gain_muscle": "Ganar m\u00fasculo",
                "maintain": "Mantener peso", "improve_health": "Mejorar salud",
                "eat_healthier": "Comer m\u00e1s sano"}
    activity_map = {"sedentary": "Sedentario", "lightly_active": "Poco activo",
                    "light": "Poco activo", "moderate": "Moderado",
                    "active": "Activo", "very_active": "Muy activo"}

    basic = (
        f"\U0001f464 *Tu perfil*\n\n"
        f"Nombre: {user.get('name', '?')}\n"
        f"Edad: {user.get('age', '?')} a\u00f1os\n"
        f"Peso: {user.get('weight_kg', '?')} kg\n"
        f"Altura: {user.get('height_cm', '?')} cm\n"
        f"Objetivo: {goal_map.get(user.get('goal', ''), user.get('goal', '?'))}\n"
        f"Actividad: {activity_map.get(user.get('activity_level', ''), user.get('activity_level', '?'))}"
    )

    profile_text = user.get("profile_text", "")
    if profile_text:
        basic += f"\n\n\U0001f4dd *Lo que s\u00e9 de vos:*\n{profile_text[:800]}"
    else:
        basic += "\n\n\u26a0\ufe0f _No tengo tu perfil detallado. Hac\u00e9 /start para rehacer el onboarding._"

    basic += "\n\n_Para modificar tu perfil us\u00e1 /reset_"
    await update.message.reply_text(basic, parse_mode="Markdown")

async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await update.message.reply_text("Primero configurÃ¡ tu perfil con /start.")
        return
    deleted = db.delete_last_meal(telegram_id)
    if deleted:
        await update.message.reply_text(f"ðŸ—‘ EliminÃ© tu Ãºltima comida registrada: _{deleted}_", parse_mode="Markdown")
    else:
        await update.message.reply_text("No encontrÃ© comidas registradas para eliminar.")

