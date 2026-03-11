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

SYSTEM_BASE = (
    "Sos un coach de nutrición personal, cálido y alentador. "
    "Hablás en español rioplatense, usás 'vos' en lugar de 'tú'. "
    "Tus respuestas son MUY cortas: máximo 2-3 líneas, sin explicaciones largas. "
    "Usás emojis de forma natural. Nunca sos sermoneador ni pesado. "
    "Conversacional y directo al punto."
)


async def _ask(messages: list, system: str = SYSTEM_BASE) -> str:
    try:
        client = get_client()
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system,
            messages=messages,
        )
        return resp.content[0].text.strip()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] Claude error: {type(e).__name__}: {e}")
        return "Uy, tuve un problemita técnico 😅 Intentá de nuevo en un momento."


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


async def analyze_meal_text(description: str, user: dict) -> dict:
    profile = f"Objetivo: {user['goal']}, Actividad: {user['activity_level']}, Peso: {user['weight_kg']}kg"
    prompt = (
        f"El usuario describió su comida: '{description}'\n"
        f"Perfil del usuario: {profile}\n\n"
        "Respondé con:\n"
        "1. Qué detectaste que comió\n"
        "2. Estimación de calorías (número solo)\n"
        "3. Tipo de comida (breakfast/lunch/dinner/snack)\n"
        "4. Si se alinea con su objetivo (sí/no/parcialmente)\n"
        "5. Un tip corto y práctico\n"
        "6. Estimación de macros en gramos (proteínas, carbohidratos, grasas)\n\n"
        "Formato de respuesta (JSON):\n"
        '{"detected": "...", "calories": 450, "proteins_g": 25, "carbs_g": 45, "fats_g": 15, "meal_type": "lunch", "aligned": "sí", "tip": "...", "full_response": "mensaje amigable al usuario"}'
    )
    raw = await _ask([{"role": "user", "content": prompt}])
    return _parse_meal_json(raw)


async def analyze_meal_photo(photo_path: str, user: dict) -> dict:
    try:
        with open(photo_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        ext = photo_path.rsplit(".", 1)[-1].lower()
        media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        media_type = media_map.get(ext, "image/jpeg")
    except Exception as e:
        print(f"[ai] Photo read error: {e}")
        return await analyze_meal_text("una comida (no se pudo leer la foto)", user)

    profile = f"Objetivo: {user['goal']}, Actividad: {user['activity_level']}, Peso: {user['weight_kg']}kg"
    prompt = (
        f"Analizá esta foto de comida del usuario.\n"
        f"Perfil: {profile}\n\n"
        "Respondé con:\n"
        "1. Qué detectaste que comió\n"
        "2. Estimación de calorías (número solo)\n"
        "3. Tipo de comida (breakfast/lunch/dinner/snack)\n"
        "4. Si se alinea con su objetivo\n"
        "5. Un tip corto\n\n"
        "Formato JSON:\n"
        '{"detected": "...", "calories": 450, "proteins_g": 25, "carbs_g": 45, "fats_g": 15, "meal_type": "lunch", "aligned": "sí", "tip": "...", "full_response": "mensaje amigable al usuario"}'
    )

    try:
        client = get_client()
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM_BASE,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        raw = resp.content[0].text.strip()
        return _parse_meal_json(raw)
    except Exception as e:
        print(f"[ai] Vision error: {e}")
        return {
            "detected": "tu comida",
            "calories": 0,
            "meal_type": "snack",
            "aligned": "parcialmente",
            "tip": "",
            "full_response": "No pude analizar bien la foto 😅 ¿Podés describirme qué comiste?"
        }


def _parse_meal_json(raw: str) -> dict:
    import json, re
    defaults = {
        "detected": "tu comida",
        "calories": 0,
        "proteins_g": 0,
        "carbs_g": 0,
        "fats_g": 0,
        "meal_type": "snack",
        "aligned": "parcialmente",
        "tip": "",
        "full_response": raw
    }
    try:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            defaults.update(data)
    except Exception:
        pass
    return defaults


async def generate_followup_message(user: dict, meal_type: str, ftype: str) -> str:
    meal_names = {
        "breakfast": "el desayuno",
        "lunch": "el almuerzo",
        "dinner": "la cena",
        "snack": "la merienda"
    }
    meal_name = meal_names.get(meal_type, "la próxima comida")

    if ftype == "reminder":
        prompt = (
            f"Mandá un recordatorio amigable y corto a {user['name']} "
            f"diciéndole que en unos 30 minutos es hora de {meal_name}. "
            "Preguntale qué tiene pensado comer. Máximo 2 oraciones."
        )
    else:
        prompt = (
            f"Mandá un check-in amigable a {user['name']} preguntándole cómo va su alimentación hoy. "
            "Máximo 2 oraciones, tono cálido."
        )
    return await _ask([{"role": "user", "content": prompt}])


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


async def check_meal_vague(text: str) -> str | None:
    """Return a follow-up question if the meal description is too vague, else None."""
    raw = await _ask(
        [{"role": "user", "content": f"Descripción de comida: '{text}'"}],
        system=(
            "Sos un validador de descripciones de comida. "
            "Si la descripción NO especifica qué alimento se comió "
            "(por ejemplo: 'comí', 'almorcé', 'desayuné', 'cené' sin mencionar qué), "
            "respondé SOLO con una pregunta corta y amigable en español rioplatense preguntando qué comió. "
            "Si la descripción menciona algún alimento concreto, respondé SOLO con la palabra 'OK'."
        ),
    )
    if raw.strip().upper() == "OK":
        return None
    return raw.strip()


async def classify_intent(text: str) -> bool:
    """Return True if the message is food/meal related."""
    raw = await _ask(
        [{"role": "user", "content": f"Message: '{text}'"}],
        system=(
            "You are an intent classifier. "
            "Reply ONLY with 'yes' if the message is about food, meals, drinks, eating, or nutrition. "
            "Reply ONLY with 'no' for anything else."
        ),
    )
    return raw.strip().lower().startswith("y")


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
