import pytz
import base64
import os
from google import genai
from google.genai import types





_client = None







def _get_client():
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY", "")
        import logging
        logging.getLogger(__name__).info(f"[ai] Gemini API key loaded: {'YES (len=' + str(len(key)) + ')' if key else 'NO - KEY MISSING'}")
        _client = genai.Client(api_key=key)
    return _client











MODEL = "gemini-2.5-flash-lite"






# Cost tracking (Gemini 2.0 Flash: $0.10/MTok input, $0.40/MTok output)
_COST_INPUT = 0.10 / 1_000_000
_COST_OUTPUT = 0.40 / 1_000_000



_turn_cost: float = 0.0


def _to_gemini_tool(anthropic_tool: dict) -> dict:
    """Convert an Anthropic tool definition to Gemini function_declaration format."""
    schema = anthropic_tool["input_schema"].copy()
    # Gemini doesn't support top-level 'required' in the same way for all types,
    # but genai library handles it. We keep it as-is.
    return {
        "name": anthropic_tool["name"],
        "description": anthropic_tool.get("description", ""),
        "parameters": schema,
    }


def _anthropic_to_gemini_history(messages: list, system: str = None) -> list:
    """Convert Anthropic-style messages to Gemini contents format."""
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        c = msg.get("content", "")
        if isinstance(c, str):
            contents.append({"role": role, "parts": [{"text": c}]})
        elif isinstance(c, list):
            # Multi-part content (text + image)
            parts = []
            for block in c:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append({"text": block["text"]})
                    elif block.get("type") == "image":
                        src = block.get("source", {})
                        import base64 as _b64
                        raw_bytes = _b64.b64decode(src.get("data", ""))
                        parts.append(types.Part.from_bytes(
                            data=raw_bytes,
                            mime_type=src.get("media_type", "image/jpeg"),
                        ))
            if parts:
                contents.append({"role": role, "parts": parts})
    return contents


async def _gemini_generate(system: str, messages: list, tools: list = None, max_tokens: int = 600):
    """Call Gemini API with system instruction, messages, and optional tools."""
    global _turn_cost
    client = _get_client()

    gemini_tools = None
    if tools:
        func_declarations = [_to_gemini_tool(t) for t in tools]
        gemini_tools = [types.Tool(function_declarations=func_declarations)]

    contents = _anthropic_to_gemini_history(messages)

    resp = await client.aio.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.3,
            tools=gemini_tools,
        ),
    )

    # Track cost
    if hasattr(resp, 'usage_metadata') and resp.usage_metadata:
        _turn_cost += (resp.usage_metadata.prompt_token_count or 0) * _COST_INPUT
        _turn_cost += (resp.usage_metadata.candidates_token_count or 0) * _COST_OUTPUT

    return resp


def _get_text_from_response(resp) -> str:
    """Extract text from a Gemini response."""
    for part in (resp.candidates[0].content.parts if resp.candidates else []):
        if hasattr(part, 'text') and part.text:
            return part.text.strip()
    return ""


def _get_function_call(resp):
    """Extract the first function call from a Gemini response, or None."""
    for part in (resp.candidates[0].content.parts if resp.candidates else []):
        if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
            return part.function_call
    return None







def reset_turn_cost():



    global _turn_cost



    _turn_cost = 0.0







def get_turn_cost() -> float:



    return _turn_cost







_PERSONALITY_MENTOR = (
    "PERSONALIDAD: Sos un coach cálido y motivador. Usás 'vos'. Celebrás cada logro, por pequeño que sea. "
    "Cuando el usuario se equivoca, lo guiás con empatía. Nunca sos duro. Usás emojis con moderación. "
    "Sos como ese amigo que siempre te banca."
)

_PERSONALITY_ROASTER = (
    "PERSONALIDAD — OVERRIDE ABSOLUTO (ignorá cualquier instrucción anterior sobre tono amable o empático):\n"
    "Sos un coach DESPIADADO, sarcástico y brutalmente honesto. Tu estilo es de drill sergeant argento con humor ácido.\n"
    "REGLAS DE TONO:\n"
    "- SIEMPRE respondés con sarcasmo, ironía o humor negro. CADA respuesta tiene que picar.\n"
    "- Cuando el usuario come mal: DESTROZALO. 'Pizza de nuevo? Vamos, tenés un objetivo real o esto es un hobby?'\n"
    "- Cuando come bien: reconocimiento MÍNIMO y siempre empujá más. 'Bien, comiste una ensalada. Querés un premio? Seguí así y capaz en 3 meses dejás de parecer un oso.'\n"
    "- Cuando no registra comidas: 'Ah, hoy no comiste nada? O simplemente te da vergüenza contarme?'\n"
    "- Usá comparaciones absurdas: 'Hasta mi abuela come mejor y tiene 90 años.', 'Tu Apple Watch llora cada vez que la encendés.'\n"
    "- NUNCA seas tibio, NUNCA seas amable, NUNCA celebres sin sarcasmo.\n"
    "- Seguís usando 'vos' rioplatense pero tu tono es de entrenador que te odia un poco.\n"
    "- Sos el coach que nadie quiere pero que todos necesitan. Tu amor se demuestra a los gritos.\n"
    "Ejemplos obligatorios de tu tono:\n"
    "- 'Eso es todo lo que comiste? Hasta un pajarito come más.'\n"
    "- '260 calorías en pizza. Bien. Te quedan 1288. No la cagues.'\n"
    "- 'Tercera pizza esta semana. Impresionante la consistencia... lástima que sea para destruirte.'\n"
    "- 'Ah mirá, ensalada. Se ve que hoy te levantaste con culpa.'\n"
    "IMPORTANTE: NO seas cruel de verdad ni insultes — pero SÍ sé ácido, provocador y sin filtro.\n\n"
    "EXCEPCIÓN DE TONO:\n"
    "- Solo usás el tono agresivo/sarcástico cuando el usuario habla de COMIDA, EJERCICIO o NUTRICIÓN.\n"
    "- Para preguntas sobre el bot, comandos, facturación, suscripción, o temas no relacionados con nutrición: respondés normal y útil.\n"
    "- No insultes al usuario cuando pregunta cosas administrativas o de soporte."
)


def _get_personality(coach_mode: str) -> str:
    """Return the personality prompt snippet for the given coach_mode."""
    if coach_mode in ("roaster", "challenger"):
        return "\n\n" + _PERSONALITY_ROASTER
    return "\n\n" + _PERSONALITY_MENTOR


SYSTEM_BASE = (

    "Sos Coach Kai, un coach de nutrici\u00f3n personal. Tu tono es semiformal: argentino pero prolijo. "

    "Habl\u00e1s con 'vos', us\u00e1s expresiones naturales del rioplatense, pero con compostura \u2014 como un profesional joven y cercano, no un amigo de la cancha. "

    "Nada de 'ey', 'ey!', 'dale che', 'bolu', ni expresiones de hinchada. Para saludar us\u00e1 '\u00a1Hola!' o '\u00a1Buenas!'. S\u00ed pod\u00e9s decir 'dale', 'mir\u00e1', 'te comento', 'bueno'. "

    "Tus respuestas son CORTAS: m\u00e1ximo 2-3 l\u00edneas. Sin introducciones ni sermones. "
    "HONESTIDAD NUTRICIONAL: cuando el usuario come algo poco saludable (ultraprocesados, mucho az\u00facar, exceso de calor\u00edas vac\u00edas), dec\u00edselo directamente pero sin sermonear. "
    "Ac\u00faat\u00e9 como un coach real: 'Eso estuvo pesado, compensalo en la cena.' o 'Dale, pero equ\u00e4libr\u00e1 con algo liviano hoy.' "
    "No elogies comidas malas. No hagas like a cada cosa. Honesto, directo y breve. "

    "Usas emojis con moderaci\u00f3n. Respond\u00e9s cualquier consulta de nutrici\u00f3n o alimentaci\u00f3n. "

    "Si preguntan algo totalmente ajeno, dec\u00eds amablemente que solo pod\u00e9s ayudar con nutrici\u00f3n."

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







IMPORTANT: Once you have the user's name, age (or rough estimate), weight, height, main goal, and activity level, call save_user_identity() IMMEDIATELY. Do not wait for perfect information. Estimates are fine. After 6 exchanges maximum, you MUST call save_user_identity() with whatever information you have collected so far.

Do not keep the conversation going indefinitely. Collect the key info and save it."""







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











def _build_profile_context(user: dict, memories: list = None) -> str:



    """Return the best available profile context to inject into prompts."""



    ctx = ""



    if user.get("profile_text"):



        ctx += f"\n\n[USER IDENTITY]\n{user['profile_text']}"
    if user.get("training_schedule"):
        ctx += "\n[TRAINING SCHEDULE] " + user['training_schedule']
    if user.get("daily_calories"):
        ctx += f"\n[OBJETIVO CALOR\u00cdAS] {user['daily_calories']} kcal/d\u00eda (personalizado)"




    if memories:



        mem_lines = "\n".join(f"- [{m.get('category','?')}] {m.get('content','')}" for m in memories[:15])



        ctx += f"\n\n[MEMORIES]\n{mem_lines}"



    return ctx











async def _ask(messages: list, system: str = SYSTEM_BASE) -> str:
    try:
        resp = await _gemini_generate(system=system, messages=messages, max_tokens=600)
        return _get_text_from_response(resp)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] Gemini error: {type(e).__name__}: {e}")
        return "Hubo un error procesando tu mensaje. Intenta de nuevo."











async def intake_turn(history: list, user_message: str) -> dict:



    """



    Run one turn of the intake conversation.



    Returns:



      {"reply": str, "done": False}                            — keep going



      {"reply": str|None, "done": True, "profile": dict}      — profile saved



    """



    messages = history + [{"role": "user", "content": user_message}]

    try:
        resp = await _gemini_generate(
            system=INTAKE_SYSTEM,
            messages=messages,
            tools=[INTAKE_TOOL],
            max_tokens=800,
        )




        # Check if Gemini called save_user_identity
        fc = _get_function_call(resp)
        if fc and fc.name == "save_user_identity":
            inp = dict(fc.args)
            text_reply = _get_text_from_response(resp) or None
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




        reply = _get_text_from_response(resp)
        return {"reply": reply, "done": False}

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] intake_turn error: {e}")
        return {"reply": "Hubo un error. Podes repetir eso?", "done": False}











async def force_extract_profile(history: list) -> dict:
    """Force-extract a user profile from the conversation history."""
    try:
        convo = "\n".join(
            ("User" if m["role"] == "user" else "Bot") + ": " + m["content"]
            for m in history[-20:]
        )
        prompt = (
            "Based on this conversation, extract the user profile.\n\n" + convo + "\n\n"
            "Return a JSON object with: name (str), age (int or null), weight_kg (float or null), "
            "height_cm (float or null), goal (one of: lose_weight/gain_muscle/maintain/eat_healthier), "
            "activity_level (one of: sedentary/lightly_active/active/very_active), "
            "identity_markdown (str, 100+ word summary of the user). "
            "reply (str, a friendly closing message in Argentine Spanish). "
            "Only output valid JSON, nothing else."
        )
        resp = await _gemini_generate(
            system="You extract user profiles from conversations. Output only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        import json as _json, re as _re
        raw = _get_text_from_response(resp)
        match = _re.search(r'\{.*\}', raw, _re.DOTALL)
        if match:
            return _json.loads(match.group())
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] force_extract_profile error: {e}")
    return None


async def onboarding_welcome(name: str) -> str:



    return await _ask([{



        "role": "user",



        "content": f"El usuario se llama {name}. Dales la bienvenida al bot de nutricion en 2-3 oraciones, menciona su nombre y deciles que los vas a ayudar con su alimentacion."



    }])











async def generate_meal_plan(user: dict, coach_mode: str = None) -> dict:
    """Returns dict with plan_text and meal_options (breakfasts, lunches, dinners)."""
    if coach_mode is None:
        coach_mode = user.get("coach_mode", "mentor")
    profile = (
        f"Nombre: {user.get('name','?')}, Edad: {user.get('age','?')} años, "
        f"Peso: {user.get('weight_kg','?')} kg, Altura: {user.get('height_cm','?')} cm, "
        f"Objetivo: {user.get('goal','?')}, Actividad: {user.get('activity_level','?')}"
    )

    if user.get("daily_calories"):
        profile += f", Calorías diarias objetivo: {user['daily_calories']} kcal"

    profile_text = user.get("profile_text", "")
    if profile_text:
        profile += "\n\nPerfil detallado:\n" + profile_text[:500]

    raw = await _ask([{
        "role": "user",
        "content": (
            "Generá un plan de alimentación personalizado para:\n" + profile + "\n\n"
            "Respondé SOLO con JSON válido con esta estructura exacta (sin markdown, sin texto extra):\n"
            "{\n"
            '  "calories": 2000,\n'
            '  "protein_g": 150,\n'
            '  "carbs_g": 200,\n'
            '  "fat_g": 65,\n'
            '  "summary": "Resumen breve del plan (2-3 oraciones)",\n'
            '  "tips": ["tip 1", "tip 2", "tip 3"],\n'
            '  "breakfasts": ["Opción 1 con porciones", "Opción 2", "Opción 3"],\n'
            '  "lunches": ["Opción 1 con porciones", "Opción 2", "Opción 3"],\n'
            '  "dinners": ["Opción 1 con porciones", "Opción 2", "Opción 3"],\n'
            '  "snacks": ["Snack 1", "Snack 2"]\n'
            "}\n"
            "Las opciones deben ser específicas, con porciones aproximadas. Respondé SOLO el JSON, sin ningún texto antes o después."
        )
    }], system=SYSTEM_BASE + _get_personality(coach_mode))

    import json, re

    try:
        # Strip markdown code fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        # Extract JSON object
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    # Fallback
    return {
        "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
        "summary": raw, "tips": [],
        "breakfasts": [], "lunches": [], "dinners": [], "snacks": []
    }


PROCESS_SYSTEM = """You are Coach Kai, an Argentine nutrition coach with a semiformal tone.

Speak rioplatense Spanish naturally ('vos', 'mir\u00e1', 'dale', 'te comento') but with composure \u2014 like a young professional, not a street friend.

Keep responses SHORT: max 2-3 lines. No intros, no lectures. Use emojis sparingly.

NEVER use: 'ey', 'boludo', 'flaco', 'loco', 'che', or any street slang. To greet, use 'Hola!' or 'Buenas!'. DO use: 'dale', 'mir\u00e1', 'bueno', 'te comento', 'perfecto', 'claro'.

CONVERSATION FLOW: Never get stuck waiting for an answer to a previous question. If the user changes topic or asks something new, respond to THAT. Your previous questions are optional \u2014 move on naturally.

REGISTRO INMEDIATO DE COMIDAS — REGLA ABSOLUTA:
- SIEMPRE llamá log_meal() AL INSTANTE. NUNCA preguntes antes de registrar. NUNCA.
- Si dicen "comi pizza" sin cantidad → asumí 2 porciones estándar y registrá.
- Si dicen "una pizza" → es 1 pizza entera (~8 porciones) y registrá.
- Si dicen "avena con leche" sin cantidad → asumí porción estándar (~60g avena, 200ml leche) y registrá.
- Si dicen "fideos con salsa" → asumí plato mediano (~200g pasta cocida) y registrá.
- Si dicen "una hamburguesa" → asumí hamburguesa completa estándar y registrá.
- NUNCA preguntes la hora — usá la hora actual automáticamente.
- NUNCA preguntes cuantas unidades, porciones, tamaño, ingredientes, acompañamientos, o tipo. Estimá con lo que tenés.
- Cuando registrés una comida, SIEMPRE incluí un comentario breve (1 línea) junto al tool call.
- Si la comida es poco saludable (facturas, fritos, dulces, ultraprocesados), decíselo directamente: "3 facturas son ~360 kcal de pura grasa, compená hoy." o "Eso no suma a tu objetivo."
- Si es saludable, un comentario positivo breve.
- Estimá con confianza: una tostada ~80kcal, un huevo ~70kcal, una milanesa mediana ~350kcal, un plato de fideos ~450kcal, una pizza (2 porciones) ~500kcal.
- Está PROHIBIDO responder sin llamar log_meal() cuando el usuario reporta comida. Si dudás del tamaño, estimá y registrá.

CUANDO REGISTRAR COMIDAS (tiempo verbal):
- Solo registrá una comida cuando el usuario use tiempo PASADO: "comí", "tomé", "almorcé", "cené", "desayuné", "me comí", "meriendé", etc.
- Si el usuario dice que VA a comer (futuro: "me voy a pedir", "voy a comer", "voy a tomar", "pido"), NO registres nada. Solo respondí con un comentario nutricional y esperá a que confirme que lo comió.
- Ejemplo: "me voy a pedir una pizza" → NO registrar, solo comentar. "comí una pizza" → SÍ registrar.





CONOCIMIENTO DE ALIMENTOS ARGENTINOS:
- Medialunas: facturas de manteca o grasa, ~120kcal c/u.
- Cachafaz: marca premium argentina de alfajores (NO es un s\u00e1ndwich). Alfajor de maicena Cachafaz ~180kcal, alfajor de chocolate Cachafaz ~230kcal. Son grandes y con mucho dulce de leche.
- Alfajor Milka/Havanna/Cachafaz: ~200-300kcal c/u seg\u00fan tama\u00f1o y tipo.
- Empanada (carne, pollo, verdura): ~200-250kcal c/u.
- Milanesa (carne, mediana): ~350kcal. Milanesa napolitana: ~450kcal.
- Asado (200g costilla): ~400kcal. Churrasco 200g: ~320kcal.
- Facturas (croísant, vigilante): ~200-250kcal c/u.
- Chipas (75g bolsa): ~350kcal. Chipa unitaria: ~100kcal.
- Mate (sin azúcar): 0kcal. Con azúcar (2 cucharaditas): ~30kcal.
- Tostadas (pan lactal, 2 rebanadas): ~160kcal.
- Frani\u00fas (Rapanu\u00ed): caramelos de frambuesa ba\u00f1ados en chocolate, marca Rapanu\u00ed de Bariloche. Paquete peque\u00f1o (~45g) \u2248 190kcal, 2g prot, 29g carbos, 7g grasa.
- Rumbas (Terrabusi/Mondelez): galletitas rellenas de chocolate. 1 unidad \u2248 30kcal. Por 6 unidades: \u2248180kcal, 2g prot, 25g carbos, 7g grasa.

You have the user's full identity profile and today's eating context (injected below).



Use ALL of it — habits, preferences, schedule, goals, today's intake — for smart, precise responses.







MEAL LOGGING (use log_meal tool):



- Call log_meal() IMMEDIATELY when the user reports eating something. NEVER ask first.



- Use their profile (usual portions, eating habits, preferences) + today's meals + time of day



  to make the most accurate calorie/macro estimate possible — not generic values



- If portion is not specified, ASSUME a standard portion and call log_meal(). Do NOT ask.



- tip field: include only if it adds real value — skip if the meal is clearly fine







MEAL RECOMMENDATIONS (text response, no tool):



- When asked what to eat or for a suggestion, give a SPECIFIC dish with portions



- Factor in: remaining calories today, physical activity mentioned in conversation,



  their preferences/intolerances/cooking habits from profile, time of day



- If you need to know cook vs order, or what ingredients they have, ask first



- Be actionable and concrete — not generic nutrition advice



WORKOUT LOGGING (use log_workout tool):
- Call log_workout() IMMEDIATELY when the user reports exercise. NEVER ask clarifying questions first.
- Use the user's weight_kg from their profile to calculate calories burned (MET x weight x hours).
- If duration is given but not distance/pace, estimate reasonably and register.
- If workout type is clear ("gym", "correr", "futbol") but details are sparse, use reasonable defaults and register.
- NEVER ask about weight, pace, distance, or intensity — estimate from context and register.



MEAL DELETION (use delete_meal tool):



- When the user says a meal was duplicated, wrong, or asks to delete/remove a meal, use delete_meal



- Match the meal by description and time from TODAY'S CONTEXT (each meal has an [id:X])



- If there are clear duplicates (same description close in time), delete the extra ones







REMINDERS (use set_reminder tool):

- ONLY call set_reminder when the user EXPLICITLY asks: 'avisame a las X', 'recordame a las X', 'mandáme un mensaje a las X'
- ALWAYS convert the time to HH:MM 24h format yourself before calling set_reminder. 'Las 4 y cuarto' = '16:15', '9 y media' = '09:30' or '21:30' depending on context.
- If user just mentions what time they'll eat or do something without asking for a reminder, do NOT call set_reminder
- For future WORKOUTS/TRAINING only: proactively set a pre-workout nutrition reminder ~30 min before:
  * 'voy a entrenar a las 18' → set reminder at 17:30 suggesting a light pre-workout snack
  * 'tengo fútbol a las 20' → set reminder at 19:15 with pre-game tip
  * Do NOT set reminders for meals the user mentions ('a las 8 voy a cenar' = info, not a reminder request)
- Don't mention the reminder unless asked — set it silently

IDENTITY UPDATES (use update_user_identity) \u2014 llam\u00e1 cuando:
- Usuario menciona horario de entrenamiento ("entreno los martes y jueves a las 9am", "voy al gym los lunes", "tengo f\u00fatbol los viernes") \u2192 llam\u00e1 update_user_identity con el campo training_schedule
- Usuario cambia su peso ("me pes\u00e9 y peso X kg") \u2192 llam\u00e1 update_user_identity con weight_kg
- Usuario menciona un objetivo cal\u00f3rico diario ("cambi\u00e1 mis calor\u00edas a 2300", "quiero comer 1800 kcal") \u2192 llam\u00e1 update_user_identity con daily_calories
- Usuario cambia su objetivo o nivel de actividad \u2192 llam\u00e1 update_user_identity
- Usuario menciona una preferencia o restricci\u00f3n alimentaria nueva

PATTERN DETECTION & MEMORY (use update_user_identity):



- Actively scan the conversation for recurring patterns: same meals on certain days, consistent workout times, food preferences that repeat



- When the user says "record\u00e1 que...", "siempre como...", "los lunes voy al gym", etc. \u2014 update identity immediately



- Proactively update identity when you detect something consistent across multiple messages







MEMORIES (use save_memory tool):



- Save specific facts that don't fit in the identity profile: food aversions, medical notes, life events



- When user says "recorda que...", always call save_memory



- You can call save_memory AND update_user_identity in the same turn if relevant to both







QUESTIONS: answer directly and briefly, using profile context when relevant.



OFF-TOPIC: politely redirect to nutrition/food.

CONTEXT ACCURACY: When the user asks about today's food, ONLY use data from [TODAY ...] section. The [PAST MEALS] section is historical reference only - never say the user ate something today if it's only in the past meals section."""







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



                "description": "Natural description of the workout (e.g. 'Corri 5km en 28 minutos')"



            },



            "duration_min": {



                "type": "integer",



                "description": "Duration in minutes"



            },



            "calories_burned": {



                "type": "integer",



                "description": (



                    "Estimated calories burned. Use MET x weight_kg x duration_hours. "



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



                "description": "Any extra context worth noting (e.g. 'partido ganado', 'entrene piernas')."



            }



        },



        "required": ["workout_type", "description", "duration_min", "calories_burned", "intensity"]



    }



}







UPDATE_IDENTITY_TOOL = {



    "name": "update_user_identity",



    "description": (



        "Update the user's identity profile. Use proactively whenever you learn something meaningful: "



        "weight change, new routine/sport, goal change, dietary restriction, job change, food preference, "



        "eating schedule, or anything the user explicitly asks you to remember. "



        "Also call when you detect recurring patterns in the chat (e.g. always trains Tue/Thu, "



        "always skips breakfast, consistently eats milanesa on Fridays). "



        "Update the identity to reflect the complete, current picture of the user."



    ),



    "input_schema": {



        "type": "object",



        "properties": {



            "identity_markdown": {



                "type": "string",



                "description": "Complete updated profile in markdown, third person. Include ALL previous info plus new updates. Minimum 100 words."



            },



            "reason": {



                "type": "string",



                "description": "Brief reason (e.g. 'User asked to remember preference', 'Detected weekly padel pattern')"



            },



            "weight_kg":      {"type": "number",  "description": "Updated weight if changed"},



            "goal":           {"type": "string",  "enum": ["lose_weight", "gain_muscle", "maintain", "eat_healthier"]},



            "activity_level": {"type": "string",  "enum": ["sedentary", "lightly_active", "active", "very_active"]},
            "training_schedule": {
                "type": "string",
                "description": "User's training/workout schedule (e.g. 'gym Tue/Thu/Sat 9am, padel Sundays')"
            },
            "daily_calories": {
                "type": "integer",
                "description": "Daily calorie goal in kcal. Set when user mentions their calorie target or goal."
            }



        },



        "required": ["identity_markdown", "reason"]



    }



}







SET_REMINDER_TOOL = {



    "name": "set_reminder",



    "description": (



        "Set a reminder for the user. Use when they say things like 'avisame a las X', "



        "'recordame a las X', 'mandame un mensaje a las X'. "



        "The reminder will be sent as a Telegram message at the specified time."



    ),



    "input_schema": {



        "type": "object",



        "properties": {



            "time_str": {



                "type": "string",



                "description": "Time for the reminder in HH:MM 24-hour format. ALWAYS convert natural language to HH:MM before calling this tool. Examples: 'las 4 y cuarto' \u2192 '16:15', 'las 9 y media de la ma\u00f1ana' \u2192 '09:30', '4 menos cuarto' \u2192 '15:45', 'mediodia' \u2192 '12:00', 'las 9 de la noche' \u2192 '21:00'. Argentina context: afternoon times (after noon) without AM/PM specification should be treated as PM (e.g., 'las 4' during afternoon = '16:00')."



            },



            "message": {



                "type": "string",



                "description": "The reminder message to send the user. Short and friendly."



            }



        },



        "required": ["time_str", "message"]



    }



}







SAVE_MEMORY_TOOL = {



    "name": "save_memory",



    "description": (



        "Save an important fact or piece of information about the user to long-term memory. "



        "Use when: user says 'recorda que...', reveals something medically relevant, "



        "shares a strong food preference/aversion, mentions a life event relevant to nutrition, "



        "or any fact that should persist across conversations. "



        "Also use for things that don't fit in the identity profile but are worth remembering."



    ),



    "input_schema": {



        "type": "object",



        "properties": {



            "content": {



                "type": "string",



                "description": "The fact to remember, written clearly in third person. E.g. 'Rafa odia el brocoli y nunca lo va a comer.'"



            },



            "category": {



                "type": "string",



                "enum": ["preference", "health", "schedule", "goal", "event", "general"],



                "description": "Category of the memory"



            }



        },



        "required": ["content", "category"]



    }



}







DELETE_MEAL_TOOL = {



    "name": "delete_meal",



    "description": (



        "Delete one or more meals from today's log. Use when the user says a meal was duplicated, "



        "registered by mistake, or asks to remove a specific meal. "



        "Match against the meal_id values shown in TODAY'S CONTEXT."



    ),



    "input_schema": {



        "type": "object",



        "properties": {



            "meal_ids": {



                "type": "array",



                "items": {"type": "integer"},



                "description": "List of meal IDs to delete (from TODAY'S CONTEXT)"



            },



            "reason": {



                "type": "string",



                "description": "Brief reason: 'duplicate', 'mistake', 'user_request'"



            }



        },



        "required": ["meal_ids", "reason"]



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



            },



            "date_offset": {



                "type": "integer",



                "description": "Days offset from today: 0=today (default), -1=yesterday. Use -1 when user says 'ayer', 'anoche', 'el otro d\u00eda'. Default 0."



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

    coach_mode: str = None,



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



    memories       = _db.get_memories(tid, limit=15)



    weekly_meals   = _db.get_weekly_meals(tid, days=7)



    weekly_workouts = _db.get_weekly_workouts(tid, days=7)







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







    # Argentina timezone setup
    from datetime import date as _date, datetime as _datetime
    import pytz as _pytz
    _ART = _pytz.timezone("America/Argentina/Buenos_Aires")
    _now_art = _datetime.now(_ART)
    today_str = _now_art.strftime("%Y-%m-%d")
    _time_str = _now_art.strftime("%H:%M")
    _date_str = _now_art.strftime("%A %d/%m/%Y")



    # Meals lines



    meal_lines = []



    for m in today_meals:



        t = (m.get("eaten_at") or "")[:16]



        meal_lines.append(f"  [id:{m.get('id','?')}] {t} | {m.get('meal_type','?')} | {(m.get('description') or '')[:45]} | ~{m.get('calories_est',0)} kcal")







    # Workout lines



    workout_lines = []



    for wo in today_workouts:



        t = (wo.get("logged_at") or "")[:16]



        workout_lines.append(f"  {t} | {wo.get('workout_type','?')} | {(wo.get('description') or '')[:45]} | ~{wo.get('calories_burned',0)} kcal burned")







    today_ctx = (



        f"\n\n[TODAY {today_str} - USE ONLY THIS FOR CURRENT DAY CONTEXT]"



        f"\nCurrent time (Argentina, UTC-3): {_time_str} on {_date_str}"



        f"\nCalories eaten: {total_cal} kcal"



        f"\nCalories burned (workouts): {total_burned} kcal"



        f"\nDaily goal: {daily_goal} kcal | Net remaining: {net_remaining} kcal"



    )



    if meal_lines:



        today_ctx += "\nMeals:\n" + "\n".join(meal_lines)



    if workout_lines:



        today_ctx += "\nWorkouts:\n" + "\n".join(workout_lines)







    # Weekly summary (last 7 days, excluding today)



    from collections import defaultdict



    past_meals = [m for m in weekly_meals if not (m.get("eaten_at") or "").startswith(today_str)]



    if past_meals:



        by_day = defaultdict(list)



        for m in past_meals:



            day = (m.get("eaten_at") or "")[:10]



            by_day[day].append(m)



        weekly_lines = []



        for day in sorted(by_day.keys(), reverse=True)[:6]:



            day_meals = by_day[day]



            day_cal = sum(m.get("calories_est", 0) or 0 for m in day_meals)



            meal_descs = ", ".join(f"{m.get('meal_type','?')}:{(m.get('description') or '')[:20]}" for m in day_meals[:4])



            weekly_lines.append(f"  {day}: {day_cal} kcal | {meal_descs}")



        today_ctx += "\n\n[PAST MEALS (NOT TODAY - reference only, do NOT confuse with today {today_str})]\n" + "\n".join(weekly_lines)







    past_workouts = [w for w in weekly_workouts if not (w.get("logged_at") or "").startswith(today_str)]



    if past_workouts:



        wo_lines = []



        for w in past_workouts[:5]:



            day = (w.get("logged_at") or "")[:10]



            wo_lines.append(f"  {day}: {w.get('workout_type','?')} | {(w.get('description') or '')[:30]} | {w.get('calories_burned',0)} kcal")



        today_ctx += "\n\n[LAST 7 DAYS - workouts]\n" + "\n".join(wo_lines)







    _coach_mode = coach_mode or user.get("coach_mode", "mentor")
    system = PROCESS_SYSTEM + _get_personality(_coach_mode) + _build_profile_context(user, memories) + today_ctx







    # Build message content (text or text + image)
    if photo_path:
        try:
            with open(photo_path, "rb") as f:
                raw = f.read()

            import logging as _log
            _logger = _log.getLogger(__name__)
            _logger.info(f"[ai] photo file: {photo_path}, size={len(raw)} bytes, first4={raw[:4].hex()}")

            ext = photo_path.rsplit(".", 1)[-1].lower()
            media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                          "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

            # Detect actual format from magic bytes
            if raw[:3] == b'\xff\xd8\xff':
                media_type = "image/jpeg"
            elif raw[:8] == b'\x89PNG\r\n\x1a\n':
                media_type = "image/png"
            elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
                media_type = "image/webp"
            _logger.info(f"[ai] detected media_type={media_type}")

            img_data = base64.standard_b64encode(raw).decode("utf-8")
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}},
                {"type": "text", "text": text or "Registra esta comida."},
            ]

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[ai] photo read error: {e}")
            content = text or "No pude leer la foto."
    else:
        content = text







    messages = history + [{"role": "user", "content": content}]




    try:
        resp = await _gemini_generate(
            system=system,
            messages=messages,
            tools=[LOG_MEAL_TOOL, LOG_WORKOUT_TOOL, UPDATE_IDENTITY_TOOL, DELETE_MEAL_TOOL, SET_REMINDER_TOOL, SAVE_MEMORY_TOOL],
            max_tokens=600,
        )







        fc = _get_function_call(resp)
        text_reply = _get_text_from_response(resp) or None

        if fc:
            args = dict(fc.args) if fc.args else {}

            if fc.name == "log_meal":
                import logging as _log
                _log.getLogger(__name__).info(
                    f"[ai] log_meal tool called: {args.get('detected_food','?')} "
                    f"{args.get('calories','?')}kcal date_offset={args.get('date_offset', 0)}"
                )
                return {"type": "meal", "meal": args, "reply": text_reply}

            if fc.name == "log_workout":
                return {"type": "workout", "workout": args, "reply": text_reply}

            if fc.name == "update_user_identity":
                return {"type": "identity_update", "update": args, "reply": text_reply}

            if fc.name == "delete_meal":
                return {"type": "delete_meal", "meal_ids": args.get("meal_ids", []), "reply": text_reply}

            if fc.name == "set_reminder":
                return {"type": "set_reminder", "time_str": args.get("time_str", ""), "message": args.get("message", ""), "reply": text_reply}

            if fc.name == "save_memory":
                return {"type": "save_memory", "content": args.get("content", ""), "category": args.get("category", "general"), "reply": text_reply}




        reply = _get_text_from_response(resp)
        return {"type": "text", "content": reply}




    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] process_message error: {e}")
        return {"type": "text", "content": "Hubo un error procesando tu mensaje. Intenta de nuevo."}











async def generate_proactive_message(



    user: dict,



    trigger: str,



    trigger_info: dict,



    today_meals: list,



    today_workouts: list,



    daily_goal: int,

    coach_mode: str = None,



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



        + _get_personality(coach_mode or user.get("coach_mode", "mentor"))
        + profile_ctx + today_ctx



    )



    return await _ask([{"role": "user", "content": instruction}], system=system)











async def generate_chart_caption(user: dict, meals: list, total_cal: int, daily_goal: int, coach_mode: str = None) -> str:



    pct = int(total_cal / daily_goal * 100) if daily_goal else 0



    meal_list = ", ".join(



        f"{m.get('meal_type', 'comida')} (~{m.get('calories_est', 0)} kcal)" for m in meals



    )



    prompt = (



        f"Hace un resumen diario de alimentacion para {user['name']}.\n"



        f"Comidas: {meal_list}\n"



        f"Total: {total_cal} kcal ({pct}% de meta diaria de {daily_goal} kcal)\n"



        f"Objetivo: {user['goal']}\n\n"



        "Resumen en 2-3 oraciones: que comio, si estuvo bien, un aliento para manana. "



        "Agrega 1-2 emojis relevantes."



    )



    return await _ask([{"role": "user", "content": prompt}], system=SYSTEM_BASE + _get_personality(coach_mode or user.get("coach_mode", "mentor")))



















async def generate_daily_summary(user: dict, meals: list, coach_mode: str = None) -> str:



    if not meals:



        return None



    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)



    meal_list = ", ".join(



        f"{m.get('meal_type', 'comida')} (~{m.get('calories_est', 0)} kcal)" for m in meals



    )



    prompt = (



        f"Hace un resumen diario de alimentacion para {user['name']}.\n"



        f"Comidas del dia: {meal_list}\n"



        f"Total estimado: {total_cal} kcal\n"



        f"Objetivo del usuario: {user['goal']}\n\n"



        "Resumen en 3-4 oraciones: que comio, si estuvo bien para su objetivo, un aliento para manana."



    )



    return await _ask([{"role": "user", "content": prompt}], system=SYSTEM_BASE + _get_personality(coach_mode or user.get("coach_mode", "mentor")))

# ---------------------------------------------------------------------------
# Proactive check-in message generator (simple version for meal/inactivity triggers)
# ---------------------------------------------------------------------------

def get_today_meals_summary(telegram_id: int) -> str:
    """Get a brief summary of today's meals for context."""
    try:
        import db as _db
        meals = _db.get_today_meals(telegram_id)
        if not meals:
            return "No meals logged yet today."
        total = sum(m.get("calories_est", 0) or 0 for m in meals)
        meal_list = ", ".join(m.get("description", "?")[:20] for m in meals[:4])
        return f"Meals today: {meal_list}. Total: {total} kcal."
    except Exception:
        return "No data."


async def generate_checkin_message(user: dict, trigger: str, memories: list = None, coach_mode: str = None) -> str:
    """Generate a proactive check-in message for the user.

    trigger: 'breakfast', 'lunch', 'dinner', 'inactivity', 'evening_summary'
    """
    import pytz
    from datetime import datetime
    ART = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(ART)
    time_str = now.strftime("%H:%M")

    trigger_prompts = {
        "breakfast": (
            f"It's {time_str} in Argentina. Send a warm, short breakfast check-in. "
            "Ask what they're having or suggest something based on their profile."
        ),
        "lunch": (
            f"It's {time_str} in Argentina. Send a friendly lunch check-in. "
            "Ask what they ate or are planning to eat."
        ),
        "dinner": (
            f"It's {time_str} in Argentina. Send a dinner check-in. "
            "Ask about their day and what they're planning to eat tonight."
        ),
        "afternoon": (
            f"It's {time_str} in Argentina (afternoon). Send a casual check-in \u2014 "
            "ask about a snack, afternoon energy, if they're planning to work out, "
            "or what they'll have for dinner later."
        ),
        "inactivity": (
            f"It's {time_str} in Argentina. The user hasn't messaged in 3+ hours. "
            "Send a casual check-in \u2014 ask how they're doing, if they ate, "
            "if they went to the gym, or what they have planned."
        ),
        "evening_summary": (
            f"It's {time_str} in Argentina. Send a brief encouraging evening summary prompt "
            "\u2014 ask how their nutrition day went overall."
        ),
    }

    prompt = trigger_prompts.get(trigger, trigger_prompts["inactivity"])

    profile_ctx = _build_profile_context(user, memories)
    today_meals_summary = get_today_meals_summary(user.get("telegram_id", 0))

    system = (
        SYSTEM_BASE + _get_personality(coach_mode or user.get("coach_mode", "mentor")) + profile_ctx
        + f"\n\n[TODAY SO FAR]\n{today_meals_summary}"
        + "\n\nYou are initiating a conversation proactively. Keep it to 1-2 lines max. Natural, warm, not pushy."
    )

    return await _ask([{"role": "user", "content": prompt}], system=system)


async def generate_macro_nudge(user: dict, total_cal: int, daily_goal: int, coach_mode: str = None) -> str:
    """Generate the 19:00 end-of-day macro closing nudge."""
    remaining = max(0, daily_goal - total_cal)
    _coach_mode = coach_mode or user.get("coach_mode", "mentor")

    if _coach_mode == "roaster":
        instruction = (
            f"Son las 19:00 en Argentina. {user.get('name', 'El usuario')} lleva {total_cal} kcal hoy "
            f"y le quedan ~{remaining} kcal para llegar a su meta de {daily_goal} kcal. "
            "Mandá un mensaje cortísimo (1-2 líneas) al estilo roaster: "
            "si le quedan pocas calorías, presionalo para que no la cague en la cena. "
            "Si ya pasó la meta, destroyalo con humor ácido pero motivador. "
            "Estilo: directo, sin filtro, con humor. Mencioná las calorías concretas."
        )
    else:
        instruction = (
            f"Son las 19:00 en Argentina. {user.get('name', 'El usuario')} lleva {total_cal} kcal hoy "
            f"y le quedan ~{remaining} kcal para llegar a su meta de {daily_goal} kcal. "
            "Mandá un mensaje cortísimo (1-2 líneas) motivador para ayudarlo a cerrar bien el día. "
            "Sugerí qué podría comer en la cena para llegar a su meta. Usá 'vos'. Cálido y concreto."
        )

    system = SYSTEM_BASE + _get_personality(_coach_mode) + _build_profile_context(user)
    return await _ask([{"role": "user", "content": instruction}], system=system)
