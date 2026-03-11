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
    "Sos un coach de nutrición personal, cálido y alentador. "
    "Hablás en español rioplatense, usás 'vos' en lugar de 'tú'. "
    "Tus respuestas son MUY cortas: máximo 2-3 líneas, sin explicaciones largas. "
    "Usás emojis de forma natural. Nunca sos sermoneador ni pesado. "
    "Conversacional y directo al punto."
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
    import nutrition as nutr

    # Step 1: Ask Claude to extract food name + portion from the description
    extraction = await _ask(
        [{"role": "user", "content": f"Comida: '{description}'\nRespondé SOLO con JSON: {{\"food\": \"nombre del alimento principal\", \"portion\": \"descripción de la porción (ej: 200g, un plato grande, 2 unidades)\"}}"}],
        system="Sos un extractor de datos de comidas. Respondé solo con JSON, sin explicaciones."
    )
    food_name, portion = description, description
    try:
        import json, re
        m = re.search(r'\{.*\}', extraction, re.DOTALL)
        if m:
            extracted = json.loads(m.group())
            food_name = extracted.get("food", description)
            portion = extracted.get("portion", description)
    except Exception:
        pass

    # Step 2: Try Open Food Facts for real nutritional data
    off_data = await nutr.get_nutrition_for_meal(food_name, portion)

    profile = f"Objetivo: {user['goal']}, Actividad: {user['activity_level']}, Peso: {user['weight_kg']}kg"

    if off_data:
        # Use real data — ask Claude only for meal_type, alignment and tip
        prompt = (
            f"El usuario comió: '{description}'\n"
            f"Perfil: {profile}\n"
            f"Datos nutricionales reales: {off_data['calories']} kcal, {off_data['proteins_g']}g proteína, {off_data['carbs_g']}g carbos, {off_data['fats_g']}g grasa\n\n"
            "Respondé SOLO con JSON:\n"
            '{"meal_type": "lunch", "aligned": "sí", "tip": "..."}'
        )
        raw = await _ask([{"role": "user", "content": prompt}])
        extra = {}
        try:
            import json, re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                extra = json.loads(m.group())
        except Exception:
            pass

        detected = off_data["food_name"]
        cal = off_data["calories"]
        p = off_data["proteins_g"]
        c = off_data["carbs_g"]
        f = off_data["fats_g"]
        source_note = "📊 _datos: Open Food Facts_"
        return {
            "detected": detected,
            "calories": cal,
            "proteins_g": p,
            "carbs_g": c,
            "fats_g": f,
            "meal_type": extra.get("meal_type", "snack"),
            "aligned": extra.get("aligned", "parcialmente"),
            "tip": extra.get("tip", ""),
            "full_response": f"🍽 {detected} · ~{cal} kcal\n🥩 Proteína: {p}g · 🌾 Carbos: {c}g · 🫒 Grasa: {f}g\n{source_note}",
        }

    # Fallback: Claude estimation
    prompt = (
        f"El usuario describió su comida: '{description}'\n"
        f"Perfil del usuario: {profile}\n\n"
        "Respondé con:\n"
        "1. Qué detectaste que comió\n"
        "2. Estimación de calorías (número solo)\n"
        "3. Tipo de comida (breakfast/lunch/dinner/snack)\n"
        "4. Si se alinea con su objetivo (sí/no/parcialmente)\n"
        "5. Un tip corto y práctico (1 oración máximo)\n"
        "6. Estimación de macros en gramos (proteínas, carbohidratos, grasas)\n\n"
        "El campo 'full_response' debe ser SOLO el resumen nutricional en este formato exacto:\n"
        "'🍽 [nombre del plato] · ~[X] kcal\\n🥩 Proteína: [X]g · 🌾 Carbos: [X]g · 🫒 Grasa: [X]g\\n⚠️ _estimación Claude_'\n\n"
        "Formato de respuesta (JSON):\n"
        '{"detected": "...", "calories": 450, "proteins_g": 25, "carbs_g": 45, "fats_g": 15, "meal_type": "lunch", "aligned": "sí", "tip": "...", "full_response": "..."}'
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
    """Return a follow-up question if the meal description needs more detail, else None."""
    raw = await _ask(
        [{"role": "user", "content": f"Descripción de comida: '{text}'"}],
        system=(
            "Sos un validador de descripciones de comida. "
            "Para poder estimar calorías correctamente, la descripción necesita mencionar TANTO el alimento COMO la cantidad aproximada. "
            "Si falta el alimento (ej: 'comí', 'almorcé' sin decir qué) → preguntá qué comió. "
            "Si tiene el alimento pero falta la cantidad (ej: 'comí pasta', 'comí arroz') → preguntá la cantidad aproximada (ej: '¿Cuánto aprox? ¿Un plato chico, mediano o grande?'). "
            "Si tiene AMBOS (alimento + cantidad aproximada, ej: 'comí un plato grande de pasta con tuco') → respondé SOLO con 'OK'. "
            "Hacé UNA sola pregunta corta, en español rioplatense."
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
