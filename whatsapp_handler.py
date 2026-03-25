"""
WhatsApp handler — replaces handlers.py for the Twilio channel.
Onboarding is a simple state machine stored in users.onboarding_step.
After onboarding, all messages go through ai.process_message() just like the Telegram bot.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta

import httpx
import pytz

import ai
import db

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")

_BA_TZ = pytz.timezone("America/Argentina/Buenos_Aires")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _phone_to_tid(phone: str) -> int:
    """Derive a stable positive integer from a phone number to use as telegram_id."""
    import hashlib
    h = int(hashlib.sha256(phone.encode()).hexdigest(), 16)
    return h % (2 ** 31 - 1) + 1


def get_or_create_user(numero: str) -> dict:
    user = db.get_user_by_phone(numero)
    if user is None:
        tid = _phone_to_tid(numero)
        db.upsert_user(tid, phone=numero)
        user = db.get_user_by_phone(numero)
    return user


async def download_media_to_file(url: str) -> str:
    """Download Twilio media, save to photos/, return local file path."""
    os.makedirs("photos", exist_ok=True)
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, auth=auth, follow_redirects=True)
        content_type = r.headers.get("content-type", "image/jpeg")
        ext = content_type.split("/")[-1].split(";")[0].strip().lower()
        if ext not in ("jpeg", "jpg", "png", "webp"):
            ext = "jpg"
        fname = f"photos/wa_{uuid.uuid4().hex}.{ext}"
        with open(fname, "wb") as f:
            f.write(r.content)
    return fname


# ------------------------------------------------------------------
# Onboarding maps
# ------------------------------------------------------------------

GOALS = {"1": "lose_weight", "2": "gain_muscle", "3": "maintain"}
ACTIVITIES = {"1": "sedentary", "2": "lightly_active", "3": "active", "4": "very_active"}
COACH_MODES = {"1": "mentor", "2": "roaster"}


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

async def handle_message(numero: str, text: str, media_url: str = None) -> str:
    text = (text or "").strip()
    user = get_or_create_user(numero)
    tid  = user["telegram_id"]

    db.update_last_seen(tid)

    # /reset works at any point
    if text.lower() == "/reset":
        db.upsert_user(
            tid,
            onboarding_complete=0,
            onboarding_step=None,
            name=None,
            age=None,
            weight_kg=None,
            height_cm=None,
            goal=None,
            activity_level=None,
        )
        return "Perfil reseteado. Escribi cualquier cosa para empezar de nuevo."

    step             = user.get("onboarding_step")
    onboarding_done  = user.get("onboarding_complete", 0)

    if not onboarding_done:
        return await _handle_onboarding(user, tid, step, text)

    return await _handle_main(user, tid, text, media_url)


# ------------------------------------------------------------------
# Onboarding state machine
# ------------------------------------------------------------------

async def _handle_onboarding(user: dict, tid: int, step, text: str) -> str:
    # Brand-new user — send welcome
    if step is None:
        db.upsert_user(tid, onboarding_step="awaiting_name")
        return (
            "Hola! Soy NutriBot, tu coach de nutricion personal por WhatsApp.\n\n"
            "Como te llamas?"
        )

    if step == "awaiting_name":
        name = text.strip()
        if not name:
            return "Como te llamas?"
        db.upsert_user(tid, name=name, onboarding_step="awaiting_goal")
        return (
            f"Hola {name}!\n\n"
            "Cual es tu objetivo?\n"
            "1 Bajar de peso\n"
            "2 Ganar musculo\n"
            "3 Mantenerme"
        )

    if step == "awaiting_goal":
        goal = GOALS.get(text.strip())
        if not goal:
            return "Responde con 1, 2 o 3:\n1 Bajar de peso\n2 Ganar musculo\n3 Mantenerme"
        db.upsert_user(tid, goal=goal, onboarding_step="awaiting_age")
        return "Cuantos anos tenes?"

    if step == "awaiting_age":
        try:
            age = int(text.strip())
            if not (10 <= age <= 100):
                raise ValueError
        except ValueError:
            return "Ingresa tu edad en anos (ej: 28)"
        db.upsert_user(tid, age=age, onboarding_step="awaiting_weight")
        return "Cuanto pesas en kg? (ej: 75)"

    if step == "awaiting_weight":
        try:
            weight = float(text.strip().replace(",", "."))
            if not (30 <= weight <= 300):
                raise ValueError
        except ValueError:
            return "Ingresa tu peso en kg (ej: 75.5)"
        db.upsert_user(tid, weight_kg=weight, onboarding_step="awaiting_height")
        return "Cuanto medis en cm? (ej: 175)"

    if step == "awaiting_height":
        try:
            height = float(text.strip().replace(",", "."))
            if not (100 <= height <= 250):
                raise ValueError
        except ValueError:
            return "Ingresa tu altura en cm (ej: 175)"
        db.upsert_user(tid, height_cm=height, onboarding_step="awaiting_activity")
        return (
            "Cual es tu nivel de actividad fisica?\n"
            "1 Sedentario (sin ejercicio)\n"
            "2 Poco activo (1-3 dias/semana)\n"
            "3 Activo (4-5 dias/semana)\n"
            "4 Muy activo (6-7 dias/semana)"
        )

    if step == "awaiting_activity":
        activity = ACTIVITIES.get(text.strip())
        if not activity:
            return "Responde con 1, 2, 3 o 4:\n1 Sedentario\n2 Poco activo\n3 Activo\n4 Muy activo"
        db.upsert_user(tid, activity_level=activity, onboarding_step="awaiting_coach")
        return (
            "Que tipo de coach queres?\n"
            "1 Mentor - Te apoyo con carino\n"
            "2 Roaster - Sin filtro, te digo todo"
        )

    if step == "awaiting_coach":
        coach_mode = COACH_MODES.get(text.strip())
        if not coach_mode:
            return "Responde con 1 o 2:\n1 Mentor\n2 Roaster"
        db.upsert_user(tid, coach_mode=coach_mode, onboarding_complete=1, onboarding_step="done")

        fresh_user = db.get_user_by_phone(user.get("phone", ""))
        name = (fresh_user or user).get("name", "")

        try:
            plan = await ai.generate_meal_plan(fresh_user or user, coach_mode=coach_mode)
            plan_text = plan.get("text", "") if isinstance(plan, dict) else str(plan)
        except Exception as e:
            logger.warning(f"[onboarding] meal plan error: {e}")
            plan_text = ""

        msg = f"Listo {name}! Ya tenes tu perfil. "
        if plan_text:
            msg += f"\n\nAca va tu plan personalizado:\n\n{plan_text}\n\n"
        msg += (
            "Ahora podes enviarme fotos o texto de tus comidas para analizarlas.\n\n"
            "Comandos:\n"
            "/stats - resumen del dia\n"
            "/plan - ver tu plan\n"
            "/coach - cambiar tipo de coach\n"
            "/reset - empezar de nuevo"
        )
        return msg

    # Unknown step — restart
    db.upsert_user(tid, onboarding_step=None)
    return "Algo salio mal. Como te llamas?"


# ------------------------------------------------------------------
# Main mode
# ------------------------------------------------------------------

async def _handle_main(user: dict, tid: int, text: str, media_url: str = None) -> str:
    text_lower = text.lower()

    # Mid-session coach change
    if user.get("onboarding_step") == "awaiting_coach":
        coach_mode = COACH_MODES.get(text.strip())
        if coach_mode:
            db.upsert_user(tid, coach_mode=coach_mode, onboarding_step="done")
            label = "Mentor" if coach_mode == "mentor" else "Roaster"
            return f"Coach cambiado a {label}."
        return "Responde con 1 o 2:\n1 Mentor\n2 Roaster"

    # Commands
    if text_lower.startswith("/stats"):
        return await _cmd_stats(user, tid)

    if text_lower.startswith("/plan"):
        return await _cmd_plan(user)

    if text_lower.startswith("/coach"):
        db.upsert_user(tid, onboarding_step="awaiting_coach")
        return (
            "Que tipo de coach queres?\n"
            "1 Mentor - Te apoyo con carino\n"
            "2 Roaster - Sin filtro, te digo todo"
        )

    if text_lower.startswith("/start"):
        return (
            "Ya estas registrado. "
            "Enviame una foto o texto de tu comida para analizarla.\n"
            "Usa /stats para ver el resumen del dia."
        )

    # Photo
    if media_url:
        return await _handle_photo(user, tid, text, media_url)

    # Plain text
    if not text:
        return "Enviame una foto o descripcion de tu comida."

    return await _handle_text(user, tid, text)


async def _handle_photo(user: dict, tid: int, text: str, media_url: str) -> str:
    try:
        photo_path = await download_media_to_file(media_url)
    except Exception as e:
        logger.error(f"[handler] media download error for {tid}: {e}")
        return "No pude descargar la imagen. Intenta de nuevo o describe la comida con texto."

    try:
        history = db.get_chat_history(tid)
        result = await ai.process_message(
            text=text or "Analiza esta comida",
            user=user,
            history=history,
            photo_path=photo_path,
            coach_mode=user.get("coach_mode", "mentor"),
        )
        _persist_result(user, tid, result, history, text or "foto de comida")
        return _extract_reply(result)
    except Exception as e:
        logger.error(f"[handler] photo process error for {tid}: {e}")
        return "No pude analizar la foto. Describe la comida con texto e intenta de nuevo."


async def _handle_text(user: dict, tid: int, text: str) -> str:
    try:
        history = db.get_chat_history(tid)
        result = await ai.process_message(
            text=text,
            user=user,
            history=history,
            coach_mode=user.get("coach_mode", "mentor"),
        )
        _persist_result(user, tid, result, history, text)
        return _extract_reply(result)
    except Exception as e:
        logger.error(f"[handler] process_message error for {tid}: {e}")
        return "Hubo un error procesando tu mensaje. Intenta de nuevo."


# ------------------------------------------------------------------
# Persistence helpers
# ------------------------------------------------------------------

def _extract_reply(result: dict) -> str:
    if result.get("type") == "meal":
        return result.get("reply") or "Comida registrada."
    return result.get("content", "")


def _persist_result(user: dict, tid: int, result: dict, history: list, user_text: str):
    if result.get("type") == "meal":
        meal = result.get("meal", {})
        if meal:
            detected = (
                meal.get("detected_food")
                or meal.get("description")
                or meal.get("detected", "comida")
            )
            calories = meal.get("calories_est") or meal.get("calories", 0) or 0
            try:
                calories = int(calories)
            except (ValueError, TypeError):
                calories = 0

            date_offset = int(meal.get("date_offset") or 0)
            eaten_at = (datetime.now(_BA_TZ) + timedelta(days=date_offset)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            db.add_meal(
                user_id=user["id"],
                telegram_id=tid,
                description=str(detected)[:500],
                photo_path="",
                calories_est=calories,
                meal_type=meal.get("meal_type", "snack"),
                claude_analysis="",
                proteins_g=float(meal.get("proteins_g", 0) or 0),
                carbs_g=float(meal.get("carbs_g", 0) or 0),
                fats_g=float(meal.get("fats_g", 0) or 0),
                eaten_at=eaten_at,
            )

    reply_text = _extract_reply(result)
    new_history = history + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": reply_text},
    ]
    db.save_chat_history(tid, new_history[-40:])


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

async def _cmd_stats(user: dict, tid: int) -> str:
    meals = db.get_today_meals(tid)
    if not meals:
        return "No registraste ninguna comida hoy. Empieza enviando una foto o texto."

    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)
    total_p   = sum(m.get("proteins_g",  0) or 0 for m in meals)
    total_c   = sum(m.get("carbs_g",     0) or 0 for m in meals)
    total_f   = sum(m.get("fats_g",      0) or 0 for m in meals)

    lines = [f"Resumen de hoy ({len(meals)} comida{'s' if len(meals) != 1 else ''}):\n"]
    for m in meals:
        cal  = m.get("calories_est", 0) or 0
        desc = (m.get("description") or "comida")[:40]
        lines.append(f"- {desc} — {cal} kcal")
    lines.append(f"\nTotal: {total_cal} kcal")
    lines.append(f"Proteinas: {total_p:.0f}g | Carbos: {total_c:.0f}g | Grasas: {total_f:.0f}g")
    return "\n".join(lines)


async def _cmd_plan(user: dict) -> str:
    try:
        plan = await ai.generate_meal_plan(user, coach_mode=user.get("coach_mode", "mentor"))
        if isinstance(plan, dict):
            return plan.get("text", "No pude generar el plan.")
        return str(plan)
    except Exception as e:
        logger.error(f"[handler] /plan error: {e}")
        return "No pude generar el plan ahora. Intenta mas tarde."
