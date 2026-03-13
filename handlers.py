import os

import logging

from datetime import datetime, timedelta



import pytz

from telegram import Update

from telegram.ext import ContextTypes



import ai

import db

import charts as charts_module

import scheduler as sched_module



logger = logging.getLogger(__name__)



_BA_TZ = pytz.timezone("America/Argentina/Buenos_Aires")





# ---------------------------------------------------------------------------

# Helpers

# ---------------------------------------------------------------------------



def _onboarding_url(telegram_id: int) -> str:

    token = db.create_onboarding_token(telegram_id)

    base_url = os.environ.get("WEB_BASE_URL", "http://localhost:8080")

    return f"{base_url}/onboarding/{token}"





def _daily_goal(user: dict) -> int:

    """Estimate daily calorie goal based on user profile (Mifflin-St Jeor male)."""

    weight = user.get("weight_kg") or 70

    height = user.get("height_cm") or 170

    age = user.get("age") or 25

    goal = user.get("goal", "maintain")

    activity = user.get("activity_level", "moderate")



    bmr = 10 * weight + 6.25 * height - 5 * age + 5

    activity_mult = {

        "sedentary": 1.2,

        "light": 1.375,

        "lightly_active": 1.375,

        "moderate": 1.55,

        "active": 1.725,

        "very_active": 1.9,

    }

    tdee = bmr * activity_mult.get(activity, 1.55)



    if goal == "lose_weight":

        tdee -= 400

    elif goal == "gain_muscle":

        tdee += 300



    return int(tdee)





# ---------------------------------------------------------------------------

# Meal helper

# ---------------------------------------------------------------------------



async def _save_and_reply_meal(update: Update, user: dict, result: dict):

    """Save a meal to the DB and send the formatted reply."""

    meal = result.get("meal", result)



    detected = (

        meal.get("detected_food")

        or meal.get("description")

        or meal.get("detected", "comida")

    )

    calories = meal.get("calories_est") or meal.get("calories", 0) or 0

    proteins = float(meal.get("proteins_g", 0) or 0)

    carbs = float(meal.get("carbs_g", 0) or 0)

    fats = float(meal.get("fats_g", 0) or 0)

    meal_type = meal.get("meal_type", "snack")



    try:

        calories = int(calories)

    except (ValueError, TypeError):

        calories = 0



    telegram_id = update.effective_user.id



    db.add_meal(

        user_id=user["id"],

        telegram_id=telegram_id,

        description=detected[:500],

        photo_path="",

        calories_est=calories,

        meal_type=meal_type,

        claude_analysis="",

        proteins_g=proteins,

        carbs_g=carbs,

        fats_g=fats,

    )



    today_meals = db.get_today_meals(telegram_id)

    total_cal = sum(m.get("calories_est", 0) or 0 for m in today_meals)

    daily_goal = _daily_goal(user)



    tip = result.get("tip") or meal.get("tip", "")



    lines = [

        f"\u2705 *{detected}* \u2014 ~{calories} kcal",

        f"\U0001f969 {proteins:.0f}g prot  \U0001f33e {carbs:.0f}g carbos  \U0001fab2 {fats:.0f}g grasa",

        f"\U0001f4ca Hoy: {total_cal} / {daily_goal} kcal",

    ]

    if tip:

        lines.append(f"\n\U0001f4ac {tip}")



    reply = "\n".join(lines)

    try:

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception:

        await update.message.reply_text(reply.replace("*", "").replace("_", ""))





# ---------------------------------------------------------------------------

# Commands

# ---------------------------------------------------------------------------



async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    db.upsert_user(telegram_id, onboarding_complete=0)
    context.user_data.clear()
    db.clear_intake_history(telegram_id)

    # Start conversational intake
    ai.reset_turn_cost()
    result = await ai.intake_turn([], "hola, quiero empezar con el bot")
    reply = result.get("reply") or (
        "\u00a1Hola! Soy Coach Kai, tu coach personal de nutrici\u00f3n \U0001f957\n"
        "\u00bfC\u00f3mo te llam\u00e1s?"
    )

    history = [
        {"role": "user", "content": "hola, quiero empezar con el bot"},
        {"role": "assistant", "content": reply},
    ]
    db.save_intake_history(telegram_id, history)
    context.user_data["intake_history"] = history  # keep in RAM as cache too

    await update.message.reply_text(reply)





async def cmd_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)

    if not user or not user.get("onboarding_complete"):

        await update.message.reply_text(

            "Todav\u00eda no configuraste tu perfil. Us\u00e1 /start para empezar."

        )

        return



    goal_map = {

        "lose_weight": "Bajar de peso",

        "gain_muscle": "Ganar m\u00fasculo",

        "maintain": "Mantener peso",

        "eat_healthier": "Comer m\u00e1s sano",

        "improve_health": "Mejorar salud",

    }

    activity_map = {

        "sedentary": "Sedentario",

        "light": "Actividad leve",

        "lightly_active": "Actividad leve",

        "moderate": "Moderado",

        "active": "Activo",

        "very_active": "Muy activo",

    }



    await update.message.reply_text(

        f"\U0001f464 *Tu perfil*\n\n"

        f"Nombre: {user.get('name', '?')}\n"

        f"Edad: {user.get('age', '?')} a\u00f1os\n"

        f"Peso: {user.get('weight_kg', '?')} kg\n"

        f"Altura: {user.get('height_cm', '?')} cm\n"

        f"Objetivo: {goal_map.get(user.get('goal', ''), user.get('goal', '?'))}\n"

        f"Actividad: {activity_map.get(user.get('activity_level', ''), user.get('activity_level', '?'))}\n\n"

        "_Para modificar tu perfil us\u00e1 /reset_",

        parse_mode="Markdown",

    )





async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)

    if not user or not user.get("onboarding_complete"):

        await update.message.reply_text(

            "Primero necesito conocerte \U0001f60a Us\u00e1 /start."

        )

        return



    meals = db.get_today_meals(telegram_id)

    if not meals:

        await update.message.reply_text(

            "Todav\u00eda no registraste ninguna comida hoy \U0001f37d\ufe0f "

            "\u00a1Mand\u00e1me una foto o describ\u00ed qu\u00e9 comiste!"

        )

        return



    await update.message.reply_text(

        "Generando tu resumen del d\u00eda... \U0001f4ca"

    )



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





async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    db.upsert_user(
        telegram_id,
        onboarding_complete=0,
        name=None,
        age=None,
        weight_kg=None,
        height_cm=None,
        goal=None,
        activity_level=None,
    )
    context.user_data.clear()
    db.clear_intake_history(telegram_id)

    # Start conversational intake
    ai.reset_turn_cost()
    result = await ai.intake_turn([], "hola, quiero empezar de nuevo con el bot")
    reply = result.get("reply") or (
        "Perfecto, empezamos de cero \U0001f504\n"
        "Cont\u00e1me, \u00bfc\u00f3mo te llam\u00e1s?"
    )

    history = [
        {"role": "user", "content": "hola, quiero empezar de nuevo con el bot"},
        {"role": "assistant", "content": reply},
    ]
    db.save_intake_history(telegram_id, history)
    context.user_data["intake_history"] = history  # keep in RAM as cache too

    await update.message.reply_text(reply)





async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """Delete all meals registered today."""

    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)

    if not user or not user.get("onboarding_complete"):

        await update.message.reply_text(

            "Primero configur\u00e1 tu perfil con /start."

        )

        return



    today_meals = db.get_today_meals(telegram_id)

    count = 0

    for meal in today_meals:

        if db.delete_meal_by_id(telegram_id, meal["id"]):

            count += 1



    if count > 0:

        plural = "s" if count > 1 else ""

        await update.message.reply_text(

            f"\U0001f5d1 Elimin\u00e9 {count} comida{plural} de hoy. Empez\u00e1s de cero."

        )

    else:

        await update.message.reply_text(

            "No hab\u00eda comidas registradas hoy."

        )





async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)

    if not user or not user.get("onboarding_complete"):

        await update.message.reply_text(

            "Primero configur\u00e1 tu perfil con /start."

        )

        return

    deleted = db.delete_last_meal(telegram_id)

    if deleted:

        await update.message.reply_text(

            f"\U0001f5d1 Elimin\u00e9 tu \u00faltima comida registrada: _{deleted}_",

            parse_mode="Markdown",

        )

    else:

        await update.message.reply_text(

            "No encontr\u00e9 comidas registradas para eliminar."

        )





async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)

    if not user or not user.get("onboarding_complete"):

        await update.message.reply_text(

            "Primero necesito conocerte un poco \U0001f60a Us\u00e1 /start para empezar."

        )

        return

    await update.message.reply_text(

        "Armando tu plan personalizado... \U0001f957 (en unos segundos te mando el PDF)"

    )

    plan = await ai.generate_meal_plan(user)

    summary = plan.get("summary", "") if isinstance(plan, dict) else str(plan)

    await update.message.reply_text(summary)

    try:

        import pdf_generator

        from io import BytesIO



        pdf_bytes = pdf_generator.generate_plan_pdf(user, plan)

        name_slug = (user.get("name", "usuario") or "usuario").lower().replace(" ", "_")

        await update.message.reply_document(

            document=BytesIO(pdf_bytes),

            filename=f"plan_kai_{name_slug}.pdf",

            caption="\U0001f4c4 Tu plan de alimentaci\u00f3n personalizado \u2014 Coach Kai",

        )

    except Exception as e:

        logger.error(f"PDF generation error: {e}")





async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)

    if not user or not user.get("onboarding_complete"):

        await update.message.reply_text(

            "Primero necesito conocerte \U0001f60a Us\u00e1 /start."

        )

        return



    meals = db.get_today_meals(telegram_id)

    if not meals:

        await update.message.reply_text(

            "Todav\u00eda no registraste ninguna comida hoy \U0001f37d\ufe0f "

            "\u00a1Mand\u00e1me una foto o describ\u00ed lo que com\u00e9s!"

        )

        return



    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)

    total_prot = sum(float(m.get("proteins_g", 0) or 0) for m in meals)

    daily_goal = charts_module.estimate_daily_calories(user)

    pct = round(total_cal / daily_goal * 100) if daily_goal else 0

    remaining = max(0, daily_goal - total_cal)



    meal_type_names = {

        "breakfast": "Desayuno",

        "lunch": "Almuerzo",

        "dinner": "Cena",

        "snack": "Merienda",

    }

    lines = [f"\U0001f4ca *{user['name']} \u2014 hoy*\n"]

    for m in meals:

        try:

            t = datetime.fromisoformat(m["eaten_at"]).strftime("%H:%M")

        except Exception:

            t = "?"

        cal = m.get("calories_est", 0) or 0

        tipo = meal_type_names.get(m.get("meal_type", ""), "Comida")

        desc = (m.get("description", "") or "")[:35]

        lines.append(f"\u2022 {t} {tipo}: {desc} (~{cal} kcal)")



    filled = min(10, pct // 10)

    bar = "\u2588" * filled + "\u2591" * (10 - filled)

    lines.append(f"\n\U0001f525 *{total_cal} / {daily_goal} kcal* [{bar}] {pct}%")

    lines.append(f"\U0001f969 Prote\u00edna acumulada: *{total_prot:.0f}g*")

    if remaining > 0:

        lines.append(f"\U0001f4c9 Te quedan ~{remaining} kcal para hoy")

    else:

        lines.append("\u2705 \u00a1Ya alcanzaste tu meta cal\u00f3rica de hoy!")



    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")





async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "\U0001f957 *Coach Kai \u2014 Comandos disponibles*\n\n"

        "\U0001f4dd *Registrar comida:* mand\u00e1 lo que comiste en texto o foto\n"

        "   _Ej: 'com\u00ed 200g de pollo con ensalada'_\n\n"

        "/plan \u2014 Ver tu plan de alimentaci\u00f3n personalizado\n"

        "/stats \u2014 Ver estad\u00edsticas del d\u00eda\n"

        "/resumen \u2014 Gr\u00e1fico nutricional del d\u00eda\n"

        "/perfil \u2014 Ver tu perfil actual\n"

        "/limpiar \u2014 Eliminar todas las comidas de hoy\n"

        "/borrar \u2014 Eliminar la \u00faltima comida registrada\n"

        "/reset \u2014 Reiniciar tu perfil desde cero\n"

        "/ayuda \u2014 Mostrar este men\u00fa",

        parse_mode="Markdown",

    )







# ---------------------------------------------------------------------------
# Intake handler (conversational onboarding)
# ---------------------------------------------------------------------------

async def _handle_intake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a message during the onboarding intake flow."""
    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    # Load history from DB (survives Railway restarts)
    history = db.get_intake_history(telegram_id)
    # Fall back to RAM cache if DB is empty (e.g. very first message before upsert)
    if not history:
        history = context.user_data.get("intake_history", [])

    await update.message.chat.send_action("typing")
    ai.reset_turn_cost()

    # If no history at all, something went wrong - restart intake from scratch
    if not history:
        result = await ai.intake_turn([], text)
        reply = result.get("reply") or "Cont\u00e1me un poco m\u00e1s."
        new_history = [
            {"role": "user", "content": text},
            {"role": "assistant", "content": reply},
        ]
        db.save_intake_history(telegram_id, new_history)
        context.user_data["intake_history"] = new_history
        try:
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(reply.replace("*", "").replace("_", ""))
        return

    result = await ai.intake_turn(history, text)

    if result.get("done"):
        profile = result.get("profile", {})
        db.upsert_user(
            telegram_id,
            onboarding_complete=1,
            name=profile.get("name"),
            age=profile.get("age"),
            weight_kg=profile.get("weight_kg"),
            height_cm=profile.get("height_cm"),
            goal=profile.get("goal"),
            activity_level=profile.get("activity_level"),
        )
        if profile.get("identity_markdown"):
            db.save_profile_text(telegram_id, profile["identity_markdown"])

        reply = result.get("reply")
        if not reply:
            reply = (
                "\u2705 \u00a1Perfecto! Ya ten\u00e9s tu perfil listo. "
                "Ahora pod\u00e9s registrar tus comidas mand\u00e1ndome lo que com\u00eds. "
                "\u00a1Empecemos! \U0001f957"
            )
        # Clear intake history now that onboarding is done
        db.clear_intake_history(telegram_id)
        context.user_data.pop("intake_history", None)
        try:
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(reply.replace("*", "").replace("_", ""))
    else:
        reply = result.get("reply") or "Cont\u00e1me un poco m\u00e1s."
        updated_history = (history + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": reply},
        ])[-40:]
        db.save_intake_history(telegram_id, updated_history)
        context.user_data["intake_history"] = updated_history  # keep in RAM as cache too
        try:
            await update.message.reply_text(reply, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(reply.replace("*", "").replace("_", ""))

# ---------------------------------------------------------------------------

# Main message handler

# ---------------------------------------------------------------------------



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:

        return



    telegram_id = update.effective_user.id

    text = update.message.text.strip()



    user = db.get_user(telegram_id)
    if not user or not user.get("onboarding_complete"):
        await _handle_intake(update, context)
        return



    db.update_last_seen(telegram_id)

    # Maintain conversation history (keep last 100 messages)

    history = context.user_data.get("history", [])

    history = history + [{"role": "user", "content": text}]

    context.user_data["history"] = history[-20:]



    await update.message.chat.send_action("typing")

    ai.reset_turn_cost()

    result = await ai.process_message(text, user, history[:-1])



    reply = None



    if result["type"] == "meal":

        await _save_and_reply_meal(update, user, result)

        # update history with assistant reply summary

        meal = result.get("meal", result)

        detected = meal.get("detected_food") or meal.get("description") or meal.get("detected", "comida")

        calories = meal.get("calories_est") or meal.get("calories", 0) or 0

        summary = f"Registr\u00e9 tu comida: {detected} (~{calories} kcal)."

        history = history + [{"role": "assistant", "content": summary}]

        context.user_data["history"] = history[-20:]

        return



    elif result["type"] == "workout":

        workout = result.get("workout", {})

        try:

            db.add_workout(

                user_id=user["id"],

                telegram_id=telegram_id,

                workout_type=workout.get("workout_type", "other"),

                description=workout.get("description", ""),

                duration_min=int(workout.get("duration_min", 0) or 0),

                calories_burned=int(workout.get("calories_burned", 0) or 0),

                intensity=workout.get("intensity", "moderate"),

                distance_km=workout.get("distance_km"),

                notes=workout.get("notes"),

            )

        except Exception as e:

            logger.error(f"[handle_message] workout save error: {e}")



        desc = workout.get("description", "tu entrenamiento")

        burned = workout.get("calories_burned", 0) or 0

        dur = workout.get("duration_min", 0) or 0

        reply = (

            result.get("reply")

            or f"\U0001f4aa *{desc}* \u2014 {dur} min, ~{burned} kcal quemadas. \u00a1Bien hecho!"

        )



    elif result["type"] == "delete_meal":

        meal_ids = result.get("meal_ids", [])

        deleted_count = 0

        for mid in meal_ids:

            if db.delete_meal_by_id(telegram_id, mid):

                deleted_count += 1

        if deleted_count:

            plural = "s" if deleted_count > 1 else ""

            reply = (

                result.get("reply")

                or f"\U0001f5d1 Listo, elimin\u00e9 {deleted_count} comida{plural} del registro."

            )

        else:

            reply = result.get("reply") or "No encontr\u00e9 la comida para eliminar."



    elif result["type"] == "identity_update":

        update_data = result.get("update", {})

        try:

            kwargs = {}

            if update_data.get("weight_kg"):

                kwargs["weight_kg"] = update_data["weight_kg"]

            if update_data.get("goal"):

                kwargs["goal"] = update_data["goal"]

            if update_data.get("activity_level"):

                kwargs["activity_level"] = update_data["activity_level"]

            if update_data.get("identity_markdown"):

                db.save_profile_text(telegram_id, update_data["identity_markdown"])

            if kwargs:

                db.upsert_user(telegram_id, **kwargs)

        except Exception as e:

            logger.error(f"[handle_message] identity_update error: {e}")

        reply = (

            result.get("reply")

            or "\u2705 Perfecto, actualic\u00e9 tu perfil."

        )



    elif result["type"] == "set_reminder":
        time_str_orig = result.get("time_str", "")
        message = result.get("message", "")
        try:
            now = datetime.now(_BA_TZ)
            ts = time_str_orig.lower().strip()

            # Normalize: remove common words
            for word in ["las ", "la ", "kas ", "de la noche", "de la tarde", "de la mañana", "hs", "h"]:
                ts = ts.replace(word, "")
            ts = ts.strip()

            # Special cases
            if ts in ("mediodia", "mediodía"):
                h, m = 12, 0
            elif ts in ("medianoche",):
                h, m = 0, 0
            elif "y cuarto" in ts:
                h = int(ts.replace("y cuarto", "").strip().split(":")[0])
                m = 15
            elif "y media" in ts:
                h = int(ts.replace("y media", "").strip().split(":")[0])
                m = 30
            elif "menos cuarto" in ts:
                h = int(ts.replace("menos cuarto", "").strip().split(":")[0])
                m = 45
                h = h - 1
            elif ":" in ts:
                parts = ts.split(":")
                h, m = int(parts[0].strip()), int(parts[1].strip())
            else:
                h = int(float(ts.split()[0]))
                m = 0

            # PM inference: if h <= 8 and it's currently afternoon
            orig_had_pm = any(w in time_str_orig.lower() for w in ["pm", "noche", "tarde"])
            orig_had_am = any(w in time_str_orig.lower() for w in ["am", "mañana"])
            if orig_had_pm and h < 12:
                h += 12
            elif not orig_had_am and not orig_had_pm and 1 <= h <= 8 and now.hour >= 12:
                h += 12

            h = h % 24
            remind_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if remind_dt <= now:
                remind_dt += timedelta(days=1)

            import pytz as _pytz
            remind_dt_utc = remind_dt.astimezone(_pytz.utc)
            db.save_reminder(telegram_id, remind_dt_utc.isoformat(), message)
            reply = result.get("reply") or f"⏰ Listo, te aviso a las {h:02d}:{m:02d}."
        except Exception as e:
            logger.error(f"[handle_message] reminder parse error: {e}, time_str={time_str_orig!r}")
            reply = "No pude entender el horario. Podés decirme 'avisame a las 21:30' o 'recordame a las 9'."
        history = history + [{"role": "assistant", "content": reply}]
        context.user_data["history"] = history[-20:]
        await update.message.reply_text(reply)
        return



    elif result["type"] == "save_memory":

        try:

            db.save_memory(

                telegram_id=telegram_id,

                content=result.get("content", ""),

                category=result.get("category", "general"),

            )

        except Exception as e:

            logger.error(f"[handle_message] save_memory error: {e}")

        reply = (

            result.get("reply")

            or "\U0001f9e0 Anotado, lo voy a recordar."

        )



    elif result["type"] in ("chat", "text"):

        reply = result.get("content", "")



    else:

        reply = result.get("content", "No entend\u00ed. Pod\u00e9s repetirlo?")



    if not reply:

        reply = "No entend\u00ed. Pod\u00e9s repetirlo?"



    history = history + [{"role": "assistant", "content": reply}]

    context.user_data["history"] = history[-20:]



    try:

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception:

        await update.message.reply_text(reply.replace("*", "").replace("_", ""))





# ---------------------------------------------------------------------------

# Photo handler

# ---------------------------------------------------------------------------



async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id

    user = db.get_user(telegram_id)

    if not user or not user.get("onboarding_complete"):

        await update.message.reply_text(

            "Primero configur\u00e1 tu perfil con /start \U0001f60a"

        )

        return



    await update.message.reply_text(

        "Analizando tu foto... \U0001f50d"

    )



    photo = update.message.photo[-1]

    file = await context.bot.get_file(photo.file_id)

    os.makedirs("photos", exist_ok=True)

    photo_path = f"photos/{telegram_id}_{photo.file_id}.jpg"

    await file.download_to_drive(photo_path)



    caption = update.message.caption or "Registr\u00e1 esta comida."



    history = context.user_data.get("history", [])

    history = history + [{"role": "user", "content": "[foto de comida enviada]"}]

    context.user_data["history"] = history[-20:]



    await update.message.chat.send_action("typing")

    ai.reset_turn_cost()

    result = await ai.process_message(caption, user, history[:-1], photo_path=photo_path)



    if result["type"] == "meal":

        await _save_and_reply_meal(update, user, result)

        meal = result.get("meal", result)

        detected = meal.get("detected_food") or meal.get("description") or meal.get("detected", "comida")

        calories = meal.get("calories_est") or meal.get("calories", 0) or 0

        summary = f"Analiz\u00e9 la foto: {detected} (~{calories} kcal)."

    else:

        reply = result.get("content", "No pude analizar la foto. Intent\u00e1 de nuevo.")

        summary = reply

        try:

            await update.message.reply_text(reply, parse_mode="Markdown")

        except Exception:

            await update.message.reply_text(reply.replace("*", "").replace("_", ""))



    history = history + [{"role": "assistant", "content": summary}]

    context.user_data["history"] = history[-20:]

