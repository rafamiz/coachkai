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
import payments

logger = logging.getLogger(__name__)

APP_URL = os.environ.get("APP_URL", "https://coachkai-production.up.railway.app")

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
        # Create lead record for tracking; user record is created later
        db.upsert_lead(numero, source="whatsapp")
        tid = _phone_to_tid(numero)
        db.upsert_user(tid, phone=numero)
        user = db.get_user_by_phone(numero)
    return user


async def download_media_to_file(url: str) -> str:
    """Download Twilio media, save to photos/, return local file path."""
    os.makedirs("photos", exist_ok=True)
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    IMAGE_MAGIC = {
        b'\xff\xd8\xff': "image/jpeg",
        b'\x89PNG': "image/png",
        b'RIFF': "image/webp",  # RIFF....WEBP
        b'GIF8': "image/gif",
    }

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, auth=auth, follow_redirects=True)
        content_type = r.headers.get("content-type", "image/jpeg")
        body = r.content
        first50 = body[:50].hex() if body else "(empty)"
        logger.info(
            f"[download] status={r.status_code}, content_type={content_type}, "
            f"size={len(body)} bytes, first50hex={first50}"
        )

        # Si no es imagen (ej: devuelve HTML por auth fallida), tirar error claro
        is_image = any(body[:len(magic)] == magic for magic in IMAGE_MAGIC)
        if not is_image:
            preview = body[:200].decode("utf-8", errors="replace")
            logger.error(f"[download] NOT an image! Preview: {preview}")
            raise ValueError(f"Twilio returned non-image content (status={r.status_code}): {preview[:80]}")

        ext = "jpg"
        for magic, mime in IMAGE_MAGIC.items():
            if body[:len(magic)] == magic:
                ext = mime.split("/")[1]
                if ext == "jpeg":
                    ext = "jpg"
                break

        fname = f"photos/wa_{uuid.uuid4().hex}.{ext}"
        with open(fname, "wb") as f:
            f.write(body)
    return fname


# ------------------------------------------------------------------
# Onboarding maps
# ------------------------------------------------------------------

GOALS = {"1": "lose_weight", "2": "gain_muscle", "3": "maintain"}
ACTIVITIES = {"1": "sedentary", "2": "lightly_active", "3": "active", "4": "very_active"}
COACH_MODES = {"1": "mentor", "2": "roaster"}


def _check_access(tid: int) -> str | None:
    """
    Check if user has active subscription or trial.
    Returns None if access is granted, or a blocking message if not.
    """
    if db.is_user_active(tid):
        return None

    sub = db.get_subscription(tid)
    user = db.get_user(tid)
    phone = user.get("phone", "") if user else ""

    # No subscription or pending_payment — must enter card first
    if not sub or sub.get("status") == "pending_payment":
        return (
            "Para empezar tus 7 dias gratis, necesitas registrar tu tarjeta. "
            "No se te cobra nada hasta el dia 8.\n"
            f"👉 {APP_URL}/subscription/payment?phone={phone}"
        )

    if sub.get("status") == "trial":
        # Trial expired
        return (
            "Tu periodo de prueba gratuito termino.\n\n"
            "Para seguir usando CoachKai, activa tu suscripcion:\n"
            f"👉 {APP_URL}/subscription/payment?phone={phone}\n\n"
            "Son solo unos segundos y despues seguis como siempre 💪"
        )

    if sub.get("status") in ("cancelled", "past_due"):
        return (
            "Tu suscripcion esta inactiva.\n\n"
            "Reactiva tu plan para seguir usando CoachKai:\n"
            f"👉 {APP_URL}/subscription/payment?phone={phone}\n\n"
            "Te estamos esperando 💪"
        )

    # Fallback
    return None


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

async def handle_message(numero: str, text: str, media_url: str = None) -> str:
    try:
        text = (text or "").strip()
        numero = db.normalize_phone(numero)
        user = get_or_create_user(numero)
        tid  = user["telegram_id"]

        logger.info(f"[handle_message] numero={numero}, onboarding_complete={user.get('onboarding_complete')}, step={user.get('onboarding_step')}")

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

        # User is considered onboarded if onboarding_complete == 1
        if user.get("onboarding_complete") == 1:
            # Check subscription/trial access before processing
            block_msg = _check_access(tid)
            if block_msg:
                return block_msg
            return await _handle_main(user, tid, text, media_url)

        step = user.get("onboarding_step")
        return await _handle_onboarding(user, tid, step, text)
    except Exception as e:
        logger.error(f"[handle_message] UNHANDLED ERROR for {numero}: {e}", exc_info=True)
        return "Hubo un error procesando tu mensaje. Intenta de nuevo en unos minutos."


# ------------------------------------------------------------------
# Onboarding state machine
# ------------------------------------------------------------------

async def _handle_onboarding(user: dict, tid: int, step, text: str) -> str:
    # Brand-new user — send webapp link
    if step is None:
        phone = user.get("phone", "")
        db.upsert_user(tid, onboarding_step="awaiting_webapp")
        return (
            "Hola! Soy CoachKai, tu coach de nutrición personal 🤖\n\n"
            "Para empezar, completá tu perfil en 2 minutos:\n"
            f"👉 https://coachkai-production.up.railway.app/onboarding?phone={phone}\n\n"
            "Ahí elegís tu objetivo, tus datos y el tipo de coach que querés.\n"
            "Al final te cuento cómo funciona todo 💪"
        )

    # Sent webapp link, waiting for them to complete it
    if step == "awaiting_webapp":
        phone = user.get("phone", "")
        return (
            "Todavía no completaste tu perfil. Entrá acá y listo:\n"
            f"👉 https://coachkai-production.up.railway.app/onboarding?phone={phone}"
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
            plan_text = _format_plan(plan) if isinstance(plan, dict) else str(plan)
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
            "/dashboard - ver tu dashboard\n"
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

    # First message after onboarding — send welcome once
    if user.get("onboarding_step") == "done" and text_lower not in ("/stats", "/plan", "/coach", "/reset", "/start"):
        name = user.get("name", "")
        coach_mode = user.get("coach_mode", "mentor")
        coach_mode_name = "El Mentor" if coach_mode == "mentor" else "El Challenger"
        db.upsert_user(tid, onboarding_step="welcomed")
        user["onboarding_step"] = "welcomed"  # update in-memory to prevent re-trigger
        welcome = (
            f"¡Bienvenido/a {name}! 🎉 Tu perfil está listo.\n"
            f"Soy {coach_mode_name}, tu coach personal.\n"
            "Podés empezar mandándome una foto de tu próxima comida o texto de lo que comiste."
        )
        if text and not text_lower.startswith("/"):
            reply = await _handle_text(user, tid, text)
            return f"{welcome}\n\n{reply}"
        if media_url:
            reply = await _handle_photo(user, tid, text, media_url)
            return f"{welcome}\n\n{reply}"
        return welcome

    # Mid-session coach change
    if user.get("onboarding_step") == "awaiting_coach":
        coach_mode = COACH_MODES.get(text.strip())
        if coach_mode:
            db.upsert_user(tid, coach_mode=coach_mode, onboarding_step="welcomed")
            label = "Mentor" if coach_mode == "mentor" else "Roaster"
            return f"Coach cambiado a {label}."
        return "Responde con 1 o 2:\n1 Mentor\n2 Roaster"

    # Commands
    if text_lower.startswith("/stats"):
        return await _cmd_stats(user, tid)

    if text_lower.startswith("/plan"):
        return await _cmd_plan(user)

    if text_lower.startswith("/dashboard"):
        token = db.get_or_create_dashboard_token(tid)
        return (
            "Tu dashboard personal:\n"
            f"👉 {APP_URL}/dashboard/{tid}?token={token}\n\n"
            "Ahi podes ver tus calorias, macros y comidas del dia."
        )

    _CANCEL_PHRASES = [
        "cancelar", "cancelar plan", "cancelar suscripcion", "cancelar suscripción",
        "quiero cancelar", "baja mi plan", "darme de baja", "dar de baja",
        "cancela mi plan", "cancela mi suscripcion", "no quiero seguir pagando",
        "quiero cancelar mi plan", "nono quiero cancelar mi plan pago",
    ]
    if text_lower.startswith("/cancelar") or any(p in text_lower for p in _CANCEL_PHRASES):
        return await _cmd_cancelar(user, tid)

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
        return _extract_reply(result, tid, user)
    except Exception as e:
        logger.error(f"[handler] photo process error for {tid}: {e}")
        return "No pude analizar la foto. Describe la comida con texto e intenta de nuevo."


_DASHBOARD_KEYWORDS = [
    "dashboard", "mi resumen", "ver mi progreso", "mis stats", "mis estadísticas",
    "cuanto llevo", "cuánto llevo", "mi progreso", "ver mi plan",
    "resumen de hoy", "como voy", "cómo voy", "ver dashboard", "mis comidas de hoy"
]

async def _handle_text(user: dict, tid: int, text: str) -> str:
    # Auto-send dashboard if user asks about their progress
    if any(kw in text.lower() for kw in _DASHBOARD_KEYWORDS):
        token = db.get_or_create_dashboard_token(tid)
        url = f"https://coachkai-production.up.railway.app/dashboard/{tid}?token={token}"
        return f"Acá está tu resumen personalizado 📊\n{url}"

    try:
        history = db.get_chat_history(tid)
        result = await ai.process_message(
            text=text,
            user=user,
            history=history,
            coach_mode=user.get("coach_mode", "mentor"),
        )
        _persist_result(user, tid, result, history, text)
        return _extract_reply(result, tid, user)
    except Exception as e:
        logger.error(f"[handler] process_message error for {tid}: {e}", exc_info=True)
        return "Hubo un error procesando tu mensaje. Intenta de nuevo."


# ------------------------------------------------------------------
# Persistence helpers
# ------------------------------------------------------------------

def _daily_goal(user: dict) -> int:
    """Estimate daily calorie goal based on user profile (Mifflin-St Jeor male)."""
    weight = user.get("weight_kg") or 70
    height = user.get("height_cm") or 170
    age = user.get("age") or 25
    goal = user.get("goal", "maintain")
    activity = user.get("activity_level", "moderate")
    bmr = 10 * weight + 6.25 * height - 5 * age + 5
    activity_mult = {
        "sedentary": 1.2, "light": 1.375, "lightly_active": 1.375,
        "moderate": 1.55, "active": 1.725, "very_active": 1.9,
    }
    tdee = bmr * activity_mult.get(activity, 1.55)
    if goal == "lose_weight":
        tdee -= 400
    elif goal == "gain_muscle":
        tdee += 300
    return int(tdee)


def _format_meal_reply(result: dict, tid: int, user: dict) -> str:
    """Build a formatted meal reply with macros and daily progress."""
    meal = result.get("meal", {})
    detected = (
        meal.get("detected_food")
        or meal.get("description")
        or meal.get("detected", "comida")
    )
    calories = int(meal.get("calories_est") or meal.get("calories", 0) or 0)
    proteins = float(meal.get("proteins_g", 0) or 0)
    carbs = float(meal.get("carbs_g", 0) or 0)
    fats = float(meal.get("fats_g", 0) or 0)

    today_meals = db.get_today_meals(tid)
    total_cal = sum(m.get("calories_est", 0) or 0 for m in today_meals)
    daily = user.get("daily_calories") or _daily_goal(user)
    remaining = max(0, daily - total_cal)

    tip = result.get("tip") or meal.get("tip", "")

    lines = [
        f"✅ {detected} — ~{calories} kcal",
        f"🥩 {proteins:.0f}g prot | 🍞 {carbs:.0f}g carbos | 🧈 {fats:.0f}g grasa",
        f"📊 Hoy: {total_cal} / {daily} kcal (te quedan ~{remaining})",
    ]
    if tip:
        lines.append(f"\n💬 {tip}")

    return "\n".join(lines)


def _extract_reply(result: dict, tid: int = None, user: dict = None) -> str:
    rtype = result.get("type", "text")
    if rtype == "meal":
        if tid is not None and user is not None:
            return _format_meal_reply(result, tid, user)
        return result.get("reply") or "Comida registrada."
    if rtype == "workout":
        return result.get("reply") or "Ejercicio registrado."
    if rtype == "identity_update":
        return result.get("reply") or "Perfil actualizado."
    if rtype == "delete_meal":
        return result.get("reply") or "Comida eliminada."
    if rtype == "set_reminder":
        return result.get("reply") or "Recordatorio guardado."
    if rtype == "save_memory":
        return result.get("reply") or "Anotado."
    return result.get("content") or result.get("reply") or ""


def _persist_result(user: dict, tid: int, result: dict, history: list, user_text: str):
    rtype = result.get("type", "text")

    if rtype == "meal":
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

    elif rtype == "workout":
        wo = result.get("workout", {})
        if wo:
            db.add_workout(
                user_id=user["id"],
                telegram_id=tid,
                workout_type=wo.get("workout_type", "other"),
                description=str(wo.get("description", ""))[:500],
                duration_min=int(wo.get("duration_min", 0) or 0),
                calories_burned=int(wo.get("calories_burned", 0) or 0),
                intensity=wo.get("intensity", "moderate"),
                distance_km=float(wo.get("distance_km", 0) or 0) or None,
                notes=wo.get("notes"),
            )

    elif rtype == "delete_meal":
        meal_ids = result.get("meal_ids", [])
        for mid in meal_ids:
            try:
                db.delete_meal_by_id(tid, int(mid))
            except Exception as e:
                logger.warning(f"[persist] delete_meal_by_id({mid}) failed: {e}")

    elif rtype == "identity_update":
        update = result.get("update", {})
        if update:
            kwargs = {}
            if update.get("identity_markdown"):
                db.save_profile_text(tid, update["identity_markdown"])
            if update.get("weight_kg") is not None:
                kwargs["weight_kg"] = update["weight_kg"]
            if update.get("goal"):
                kwargs["goal"] = update["goal"]
            if update.get("activity_level"):
                kwargs["activity_level"] = update["activity_level"]
            if update.get("training_schedule"):
                kwargs["training_schedule"] = update["training_schedule"]
            if update.get("daily_calories") is not None:
                kwargs["daily_calories"] = update["daily_calories"]
            if kwargs:
                db.upsert_user(tid, **kwargs)

    elif rtype == "set_reminder":
        time_str = result.get("time_str", "")
        message = result.get("message", "")
        if time_str and message:
            try:
                now = datetime.now(_BA_TZ)
                h, m = map(int, time_str.split(":"))
                remind_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if remind_dt <= now:
                    remind_dt += timedelta(days=1)
                db.save_reminder(tid, remind_dt.strftime("%Y-%m-%d %H:%M:%S"), message)
            except Exception as e:
                logger.warning(f"[persist] save_reminder failed: {e}")

    elif rtype == "save_memory":
        content = result.get("content", "")
        category = result.get("category", "general")
        if content:
            db.save_memory(tid, content, category)

    reply_text = _extract_reply(result, tid, user)
    new_history = history + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": reply_text},
    ]
    db.save_chat_history(tid, new_history[-40:])


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

async def _cmd_cancelar(user: dict, tid: int) -> str:
    sub = db.get_subscription(tid)
    if not sub or sub.get("status") in ("cancelled", "pending_payment"):
        return "No tenes una suscripcion activa para cancelar."

    if sub.get("status") == "trial":
        return (
            "Estás en tu periodo de prueba gratuito. No se te va a cobrar nada si no hacés nada.\n\n"
            "Si igual querés cancelar para que no te cobren al día 8, hacelo desde MercadoPago:\n"
            "👉 https://www.mercadopago.com.ar/subscriptions"
        )

    return (
        "Para cancelar tu suscripcion, hacelo directamente desde MercadoPago:\n\n"
        "👉 https://www.mercadopago.com.ar/subscriptions\n\n"
        "Entrá con tu cuenta, buscá CoachKai y cancelá desde ahí. "
        "Tu acceso se mantiene hasta que venza el periodo actual."
    )

    mp_id = sub.get("mp_preapproval_id")
    if mp_id:
        success = payments.cancel_preapproval(mp_id)
        if success:
            db.update_subscription(tid, status="cancelled")
            return (
                "Tu suscripcion fue cancelada. "
                "Podes seguir usando CoachKai hasta que termine tu periodo actual.\n\n"
                "Si cambias de idea, escribime y te paso el link para reactivar."
            )
        else:
            return "No pude cancelar la suscripcion en este momento. Intenta de nuevo mas tarde."

    # No MP id (e.g. trial only) — just cancel locally
    db.update_subscription(tid, status="cancelled")
    return (
        "Tu suscripcion fue cancelada. "
        "Si cambias de idea, escribime y te paso el link para reactivar."
    )


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


def _format_plan(plan: dict) -> str:
    """Format a meal plan dict into readable text."""
    lines = []
    if plan.get("summary"):
        lines.append(plan["summary"])
    if plan.get("calories"):
        lines.append(f"\nObjetivo: {plan['calories']} kcal | P: {plan.get('protein_g', 0)}g | C: {plan.get('carbs_g', 0)}g | G: {plan.get('fat_g', 0)}g")
    for label, key in [("Desayuno", "breakfasts"), ("Almuerzo", "lunches"), ("Cena", "dinners"), ("Snacks", "snacks")]:
        items = plan.get(key, [])
        if items:
            lines.append(f"\n{label}:")
            for item in items:
                lines.append(f"  - {item}")
    if plan.get("tips"):
        lines.append("\nTips:")
        for tip in plan["tips"]:
            lines.append(f"  - {tip}")
    return "\n".join(lines) if lines else ""


async def _cmd_plan(user: dict) -> str:
    try:
        plan = await ai.generate_meal_plan(user, coach_mode=user.get("coach_mode", "mentor"))
        if isinstance(plan, dict):
            text = _format_plan(plan)
            return text or "No pude generar el plan."
        return str(plan)
    except Exception as e:
        logger.error(f"[handler] /plan error: {e}")
        return "No pude generar el plan ahora. Intenta mas tarde."
