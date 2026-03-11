import base64
import os
import anthropic

_client = None


def get_client():
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        import logging
        logging.getLogger(__name__).info(f"[ai] API key loaded: {'YES (len=' + str(len(key)) + ')' if key else 'NO - KEY MISSING'}")
        _client = anthropic.AsyncAnthropic(api_key=key)
    return _client


MODEL = "claude-haiku-4-5"

# Cost tracking (Haiku pricing: $0.80/MTok input, $4.00/MTok output)
_COST_INPUT = 0.80 / 1_000_000
_COST_OUTPUT = 4.00 / 1_000_000
_turn_cost: float = 0.0

def reset_turn_cost():
    global _turn_cost
    _turn_cost = 0.0

def get_turn_cost() -> float:
    return _turn_cost

SYSTEM_BASE = (
    "Sos Coach Kai, un coach de nutrición personal argentino: cálido, directo y confiable. "
    "Hablás en español rioplatense auténtico — usás 'vos', 'dale', 'buenísimo', 'te cuento', 'mirá', etc. "
    "Tus respuestas son CORTAS: máximo 2-3 líneas. Sin introducciones, sin sermones. "
    "Usás emojis con moderación. Sos como un nutricionista argentino de confianza: cercano pero profesional. "
    "NUNCA usás términos vulgares como 'boludo', 'ey', 'flaco' ni garabatos. Sí podés ser informal y genuino. "
    "Si el usuario pregunta algo de nutrición o alimentación aunque no sea para registrar comida, respondés. "
    "Si pregunta algo totalmente ajeno a nutrición, comida o salud, decís amablemente que solo podés ayudar con eso."
)

INTAKE_SYSTEM = """You are a warm, natural nutrition coach doing a first intake conversation with a new user.
Your goal is to deeply understand the user so you can give truly personalized advice.
You speak in Argentine Spanish ('vos', rioplatense), casual and friendly — like a knowledgeable friend, not a doctor.

Topics you MUST cover before saving the profile (in any natural order):
- Personal data: name, age, weight, height, where they live
- Main goal and motivation, any previous attempts
- Daily routine and work (desk job, physical work, hours, stress level)
- Physical activity: what they do, how often, intensity
- Eating habits: how many meals, rough schedule, if they eat breakfast/snacks
- What they usually eat, what they like and dislike
- Whether they cook, buy fresh ingredients, or prefer easy/fast options
- Any food intolerances or restrictions

Conversation rules:
- Ask 1-2 questions per message, never more
- If an answer is short or vague, dig deeper before moving on
- Briefly acknowledge what they said before asking the next thing
- Ask open-ended questions, not yes/no
- Be curious and natural — this is a conversation, not a form
- Do NOT rush to save the profile — make sure you have real detail on every topic

When you have gathered sufficient, detailed information on ALL topics, call save_user_identity().
Do not call it until you're confident you have a complete picture of the person."""

INTAKE_TOOL = {
    "name": "save_user_identity",
    "description": (
        "Save the complete user identity profile to the database. "
        "Only call this once you have gathered enough detail across ALL key areas: "
        "personal data, goals, lifestyle, work, training habits, and eating habits/preferences."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "identity_markdown": {
                "type": "string",
                "description": (
                    "Complete user profile written in markdown, third person, minimum 200 words. "
                    "Include all collected details: physical data, goals, lifestyle, work, training, "
                    "eating habits, food preferences, cooking habits, meal schedule, intolerances."
                )
            },
            "name":           {"type": "string", "description": "User's first name"},
            "age":            {"type": "integer", "description": "Age in years"},
            "weight_kg":      {"type": "number",  "description": "Weight in kg"},
            "height_cm":      {"type": "number",  "description": "Height in cm"},
            "goal": {
                "type": "string",
                "enum": ["lose_weight", "gain_muscle", "maintain", "eat_healthier"],
                "description": "Primary nutrition goal"
            },
            "activity_level": {
                "type": "string",
                "enum": ["sedentary", "lightly_active", "active", "very_active"],
                "description": "Overall physical activity level"
            }
        },
        "required": ["identity_markdown", "name", "weight_kg", "height_cm", "goal", "activity_level"]
    }
}


def _build_profile_context(user: dict) -> str:
    """Return the best available profile context to inject into prompts."""
    if user.get("profile_text"):
        return f"\n\n[USER IDENTITY]\n{user['profile_text']}"
    # Fallback to structured fields for users who onboarded via old web form
    goal_map = {"lose_weight": "lose weight", "gain_muscle": "gain muscle",
                "maintain": "maintain weight", "eat_healthier": "eat healthier"}
    activity_map = {"sedentary": "sedentary", "lightly_active": "lightly active",
                    "light": "lightly active", "moderate": "moderately active",
                    "active": "active", "very_active": "very active"}
    goal = goal_map.get(user.get("goal", ""), user.get("goal", "not set"))
    activity = activity_map.get(user.get("activity_level", ""), user.get("activity_level", "not set"))
    return (
        f"\nUser profile: {user.get('name')}, {user.get('age')} years old, "
        f"{user.get('weight_kg')}kg, {user.get('height_cm')}cm, "
        f"goal: {goal}, activity level: {activity}"
    )


async def _ask(messages: list, system: str = SYSTEM_BASE) -> str:
    global _turn_cost
    try:
        client = get_client()
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system,
            messages=messages,
        )
        _turn_cost += resp.usage.input_tokens * _COST_INPUT + resp.usage.output_tokens * _COST_OUTPUT
        return resp.content[0].text.strip()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] Claude error: {type(e).__name__}: {e}")
        return "Uy, tuve un problemita técnico 😅 Intentá de nuevo en un momento."


async def intake_turn(history: list, user_message: str) -> dict:
    """
    Run one turn of the intake conversation.
    Returns:
      {"reply": str, "done": False}                            — keep going
      {"reply": str|None, "done": True, "profile": dict}      — profile saved
    """
    global _turn_cost
    messages = history + [{"role": "user", "content": user_message}]
    try:
        client = get_client()
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=800,
            system=INTAKE_SYSTEM,
            tools=[INTAKE_TOOL],
            messages=messages,
        )
        _turn_cost += resp.usage.input_tokens * _COST_INPUT + resp.usage.output_tokens * _COST_OUTPUT

        # Check if Claude called save_user_identity
        for block in resp.content:
            if block.type == "tool_use" and block.name == "save_user_identity":
                inp = block.input
                text_reply = next((b.text for b in resp.content if hasattr(b, "text")), None)
                return {
                    "reply": text_reply,
                    "done": True,
                    "profile": {
                        "identity_markdown": inp.get("identity_markdown", ""),
                        "name":           inp.get("name", ""),
                        "age":            inp.get("age"),
                        "weight_kg":      inp.get("weight_kg"),
                        "height_cm":      inp.get("height_cm"),
                        "goal":           inp.get("goal", "eat_healthier"),
                        "activity_level": inp.get("activity_level", "sedentary"),
                    }
                }

        reply = next((b.text for b in resp.content if hasattr(b, "text")), "")
        return {"reply": reply.strip(), "done": False}
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] intake_turn error: {e}")
        return {"reply": "Uy, tuve un problemita 😅 ¿Podés repetir eso?", "done": False}


async def onboarding_welcome(name: str) -> str:
    return await _ask([{
        "role": "user",
        "content": f"El usuario se llama {name}. Dales la bienvenida al bot de nutrición en 2-3 oraciones, mencioná su nombre y deciles que los vas a ayudar con su alimentación."
    }])


async def generate_meal_plan(user: dict) -> str:
    profile = (
        f"Nombre: {user['name']}, Edad: {user['age']} años, "
        f"Peso: {user['weight_kg']} kg, Altura: {user['height_cm']} cm, "
        f"Objetivo: {user['goal']}, Nivel de actividad: {user['activity_level']}"
    )
    return await _ask([{
        "role": "user",
        "content": (
            f"Generá un resumen de plan de alimentación personalizado para esta persona:\n{profile}\n\n"
            "Incluí: calorías diarias aproximadas, distribución de macros, "
            "3-4 recomendaciones clave. Máximo 200 palabras, usá emojis y formato claro."
        )
    }])


PROCESS_SYSTEM = """You are Coach Kai, a warm, direct Argentine nutrition coach.
Speak in authentic rioplatense Spanish: use 'vos', 'dale', 'mirá', 'buenísimo', 'te cuento', natural Argentine expressions.
Keep responses SHORT: max 2-3 lines. No intros, no lectures. Use emojis sparingly.
Be like a trustworthy Argentine nutritionist: close and genuine, but professional. NEVER use vulgar words like 'boludo', 'ey', 'flaco'.

You have the user's full identity profile and today's eating context (injected below).
Use ALL of it — habits, preferences, schedule, goals, today's intake — for smart, precise responses.

MEAL LOGGING (use log_meal tool):
- Call log_meal() when the user clearly reports eating something, via text OR photo
- Use their profile (usual portions, eating habits, preferences) + today's meals + time of day
  to make the most accurate calorie/macro estimate possible — not generic values
- If the description is truly too vague (missing food OR missing portion), ask ONE short
  clarifying question instead of calling log_meal
- tip field: include only if it adds real value — skip if the meal is clearly fine

MEAL RECOMMENDATIONS (text response, no tool):
- When asked what to eat or for a suggestion, give a SPECIFIC dish with portions
- Factor in: remaining calories today, physical activity mentioned in conversation,
  their preferences/intolerances/cooking habits from profile, time of day
- If you need to know cook vs order, or what ingredients they have, ask first
- Be actionable and concrete — not generic nutrition advice

QUESTIONS: answer directly and briefly, using profile context when relevant.
OFF-TOPIC: politely redirect to nutrition/food."""

LOG_WORKOUT_TOOL = {
    "name": "log_workout",
    "description": (
        "Log a physical activity or workout the user just did or is reporting. "
        "Use the user's weight and the described intensity/duration to estimate calories burned accurately."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "workout_type": {
                "type": "string",
                "enum": ["running", "cycling", "walking", "football", "padel", "tennis",
                         "gym_strength", "gym_cardio", "swimming", "yoga", "boxing",
                         "basketball", "hiking", "other"],
                "description": "Category of the workout"
            },
            "description": {
                "type": "string",
                "description": "Natural description of the workout (e.g. 'Corrí 5km en 28 minutos')"
            },
            "duration_min": {
                "type": "integer",
                "description": "Duration in minutes"
            },
            "calories_burned": {
                "type": "integer",
                "description": (
                    "Estimated calories burned. Use MET × weight_kg × duration_hours. "
                    "Approximate METs: running ~10, cycling ~8, football/padel ~7, "
                    "gym_strength ~5, gym_cardio ~7, walking ~3.5, swimming ~8."
                )
            },
            "intensity": {
                "type": "string",
                "enum": ["low", "moderate", "high", "very_high"]
            },
            "distance_km": {
                "type": "number",
                "description": "Distance in km (for running, cycling, etc.). Omit if not applicable."
            },
            "notes": {
                "type": "string",
                "description": "Any extra context worth noting (e.g. 'partido ganado', 'entrené piernas')."
            }
        },
        "required": ["workout_type", "description", "duration_min", "calories_burned", "intensity"]
    }
}

UPDATE_IDENTITY_TOOL = {
    "name": "update_user_identity",
    "description": (
        "Update the user's identity profile when you learn new significant information about them. "
        "Use this when the user reveals: a weight change, a new sport or training routine, "
        "a change in goals, job change, new dietary restriction, or any other meaningful update. "
        "Do NOT call this for minor or one-off things."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "identity_markdown": {
                "type": "string",
                "description": "The complete updated profile in markdown. Include all previous info plus the new update."
            },
            "reason": {
                "type": "string",
                "description": "Brief reason for the update (e.g. 'User started training padel regularly')"
            },
            "weight_kg":      {"type": "number",  "description": "Updated weight if changed"},
            "goal":           {"type": "string",  "enum": ["lose_weight", "gain_muscle", "maintain", "eat_healthier"]},
            "activity_level": {"type": "string",  "enum": ["sedentary", "lightly_active", "active", "very_active"]}
        },
        "required": ["identity_markdown", "reason"]
    }
}

LOG_MEAL_TOOL = {
    "name": "log_meal",
    "description": (
        "Log a meal the user just ate or is currently eating. "
        "Call this when the user clearly reports food consumption via text or photo. "
        "Use the full context — user identity, today's meals, conversation history, time of day — "
        "to produce the most accurate nutritional estimate possible."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "detected_food": {
                "type": "string",
                "description": "Clean, descriptive name of what was eaten (e.g. 'Arroz con pollo, plato mediano')"
            },
            "meal_type": {
                "type": "string",
                "enum": ["breakfast", "lunch", "dinner", "snack"]
            },
            "calories": {
                "type": "integer",
                "description": "Best calorie estimate given all available context"
            },
            "proteins_g":  {"type": "number", "description": "Protein in grams"},
            "carbs_g":     {"type": "number", "description": "Carbohydrates in grams"},
            "fats_g":      {"type": "number", "description": "Fat in grams"},
            "tip": {
                "type": "string",
                "description": "One short, genuinely useful tip. Omit entirely if the meal is fine."
            },
            "aligned_with_goal": {
                "type": "string",
                "enum": ["yes", "partial", "no"],
                "description": "How well this meal aligns with the user's goal"
            }
        },
        "required": ["detected_food", "meal_type", "calories", "proteins_g", "carbs_g", "fats_g"]
    }
}


async def process_message(
    text: str,
    user: dict,
    history: list,
    photo_path: str = None,
) -> dict:
    """
    Single-call message processor. Handles logging, questions, and recommendations.

    Returns:
      {"type": "text",  "content": str}
      {"type": "meal",  "meal": dict, "reply": str | None}
    """
    global _turn_cost

    # Build today's context
    import db as _db
    tid = user.get("telegram_id", 0)
    today_meals    = _db.get_today_meals(tid)
    today_workouts = _db.get_today_workouts(tid)

    total_cal     = sum(m.get("calories_est",   0) or 0 for m in today_meals)
    total_burned  = sum(w.get("calories_burned", 0) or 0 for w in today_workouts)

    # Estimate daily goal (Mifflin-St Jeor + activity multiplier)
    w  = user.get("weight_kg") or 70
    h  = user.get("height_cm") or 170
    ag = user.get("age")       or 30
    bmr = 10 * w + 6.25 * h - 5 * ag + 5
    multipliers = {"sedentary": 1.2, "lightly_active": 1.375, "active": 1.55, "very_active": 1.725}
    daily_goal  = int(bmr * multipliers.get(user.get("activity_level", "sedentary"), 1.2))
    net_remaining = max(0, daily_goal + total_burned - total_cal)

    # Meals lines
    meal_lines = []
    for m in today_meals:
        t = (m.get("eaten_at") or "")[:16]
        meal_lines.append(f"  {t} | {m.get('meal_type','?')} | {(m.get('description') or '')[:45]} | ~{m.get('calories_est',0)} kcal")

    # Workout lines
    workout_lines = []
    for wo in today_workouts:
        t = (wo.get("logged_at") or "")[:16]
        workout_lines.append(f"  {t} | {wo.get('workout_type','?')} | {(wo.get('description') or '')[:45]} | ~{wo.get('calories_burned',0)} kcal burned")

    today_ctx = (
        f"\n\n[TODAY'S CONTEXT]"
        f"\nCalories eaten: {total_cal} kcal"
        f"\nCalories burned (workouts): {total_burned} kcal"
        f"\nDaily goal: {daily_goal} kcal | Net remaining: {net_remaining} kcal"
    )
    if meal_lines:
        today_ctx += "\nMeals:\n" + "\n".join(meal_lines)
    if workout_lines:
        today_ctx += "\nWorkouts:\n" + "\n".join(workout_lines)

    system = PROCESS_SYSTEM + _build_profile_context(user) + today_ctx

    # Build message content (text or text + image)
    if photo_path:
        try:
            with open(photo_path, "rb") as f:
                img_data = base64.standard_b64encode(f.read()).decode("utf-8")
            ext = photo_path.rsplit(".", 1)[-1].lower()
            media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                          "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}},
                {"type": "text", "text": text or "Registrá esta comida."},
            ]
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[ai] photo read error: {e}")
            content = text or "No pude leer la foto."
    else:
        content = text

    messages = history + [{"role": "user", "content": content}]

    try:
        client = get_client()
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system,
            tools=[LOG_MEAL_TOOL, LOG_WORKOUT_TOOL, UPDATE_IDENTITY_TOOL],
            messages=messages,
        )
        _turn_cost += resp.usage.input_tokens * _COST_INPUT + resp.usage.output_tokens * _COST_OUTPUT

        for block in resp.content:
            if block.type != "tool_use":
                continue
            text_reply = next((b.text for b in resp.content if hasattr(b, "text")), None)
            if block.name == "log_meal":
                return {"type": "meal", "meal": block.input, "reply": text_reply}
            if block.name == "log_workout":
                return {"type": "workout", "workout": block.input, "reply": text_reply}
            if block.name == "update_user_identity":
                return {"type": "identity_update", "update": block.input, "reply": text_reply}

        reply = next((b.text for b in resp.content if hasattr(b, "text")), "")
        return {"type": "text", "content": reply.strip()}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] process_message error: {e}")
        return {"type": "text", "content": "Uy, tuve un problemita técnico 😅 Intentá de nuevo en un momento."}


async def generate_proactive_message(
    user: dict,
    trigger: str,
    trigger_info: dict,
    today_meals: list,
    today_workouts: list,
    daily_goal: int,
) -> str:
    """
    Generate a context-aware proactive message for the scheduler.

    trigger values:
      "pre_meal"         — ~30 min before usual meal time
      "meal_followup"    — ~45 min after usual meal time, meal not logged
      "workout_checkin"  — ~20 min after usual workout end, workout not logged
    """
    profile_ctx = _build_profile_context(user)

    total_cal    = sum(m.get("calories_est",   0) or 0 for m in today_meals)
    total_burned = sum(w.get("calories_burned", 0) or 0 for w in today_workouts)
    remaining    = max(0, daily_goal + total_burned - total_cal)

    meal_lines = [
        f"  {(m.get('eaten_at') or '')[:16]} | {m.get('meal_type','?')} | {(m.get('description') or '')[:40]} | ~{m.get('calories_est',0)} kcal"
        for m in today_meals
    ]
    workout_lines = [
        f"  {(w.get('logged_at') or '')[:16]} | {w.get('workout_type','?')} | {(w.get('description') or '')[:40]} | ~{w.get('calories_burned',0)} kcal"
        for w in today_workouts
    ]

    today_ctx = (
        f"\n[TODAY: {total_cal} kcal eaten / {total_burned} kcal burned / {remaining} kcal net remaining]"
        + ("\nMeals:\n" + "\n".join(meal_lines) if meal_lines else "\nNo meals logged yet.")
        + ("\nWorkouts:\n" + "\n".join(workout_lines) if workout_lines else "\nNo workouts logged yet.")
    )

    if trigger == "pre_meal":
        meal_type = trigger_info.get("meal_type", "comida")
        meal_names = {"breakfast": "desayuno", "lunch": "almuerzo", "dinner": "cena", "snack": "merienda"}
        meal_name = meal_names.get(meal_type, meal_type)
        instruction = (
            f"Send a SHORT pre-meal reminder for {meal_name} (in ~30 min). "
            f"Use today's context: mention calories burned if they trained, suggest what kind of food would be ideal given their remaining goal. "
            f"Be specific, not generic. Max 2-3 lines."
        )
    elif trigger == "meal_followup":
        meal_type = trigger_info.get("meal_type", "comida")
        meal_names = {"breakfast": "desayuno", "lunch": "almuerzo", "dinner": "cena", "snack": "merienda"}
        meal_name = meal_names.get(meal_type, meal_type)
        instruction = (
            f"The user usually has {meal_name} around this time but hasn't logged it. "
            f"Ask casually if they already ate — keep it very short, 1 line max."
        )
    elif trigger == "workout_checkin":
        workout_type = trigger_info.get("workout_type", "entrenamiento")
        instruction = (
            f"The user usually does {workout_type} around this time and hasn't logged it today. "
            f"Ask if they trained, in a casual friendly way. If they confirm, they can tell you how it went and you'll log it. "
            f"Max 2 lines. Don't be pushy."
        )
    else:
        instruction = "Send a short friendly check-in about how their nutrition is going today. Max 2 lines."

    system = (
        "You are Coach Kai, a warm personal nutrition coach. "
        "Speak in Argentine Spanish (rioplatense, 'vos'). Be concise and natural.\n"
        + profile_ctx + today_ctx
    )
    return await _ask([{"role": "user", "content": instruction}], system=system)


async def generate_chart_caption(user: dict, meals: list, total_cal: int, daily_goal: int) -> str:
    pct = int(total_cal / daily_goal * 100) if daily_goal else 0
    meal_list = ", ".join(
        f"{m.get('meal_type', 'comida')} (~{m.get('calories_est', 0)} kcal)" for m in meals
    )
    prompt = (
        f"Hacé un resumen diario de alimentación para {user['name']}.\n"
        f"Comidas: {meal_list}\n"
        f"Total: {total_cal} kcal ({pct}% de meta diaria de {daily_goal} kcal)\n"
        f"Objetivo: {user['goal']}\n\n"
        "Resumen en 2-3 oraciones: qué comió, si estuvo bien, un aliento para mañana. "
        "Agregá 1-2 emojis relevantes."
    )
    return await _ask([{"role": "user", "content": prompt}])




async def generate_daily_summary(user: dict, meals: list) -> str:
    if not meals:
        return None
    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)
    meal_list = ", ".join(
        f"{m.get('meal_type', 'comida')} (~{m.get('calories_est', 0)} kcal)" for m in meals
    )
    prompt = (
        f"Hacé un resumen diario de alimentación para {user['name']}.\n"
        f"Comidas del día: {meal_list}\n"
        f"Total estimado: {total_cal} kcal\n"
        f"Objetivo del usuario: {user['goal']}\n\n"
        "Resumen en 3-4 oraciones: qué comió, si estuvo bien para su objetivo, un aliento para mañana."
    )
    return await _ask([{"role": "user", "content": prompt}])
