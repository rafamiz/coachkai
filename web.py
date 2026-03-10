import logging

from aiohttp import web

import ai
import db

logger = logging.getLogger(__name__)

VALID_GOALS = {"lose_weight", "gain_muscle", "maintain", "eat_healthier"}
VALID_ACTIVITIES = {"sedentary", "lightly_active", "active", "very_active"}

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_FORM_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NutriBot — Tu perfil</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f0;color:#222;padding:16px 0 40px}}
  .card{{max-width:480px;margin:0 auto;background:#fff;border-radius:18px;padding:28px 22px;box-shadow:0 2px 16px rgba(0,0,0,.09)}}
  h1{{font-size:1.45rem;margin-bottom:6px}}
  .subtitle{{color:#666;font-size:.93rem;margin-bottom:26px;line-height:1.5}}
  .field{{margin-bottom:18px}}
  label.field-label{{display:block;font-size:.88rem;font-weight:600;margin-bottom:6px;color:#444}}
  input[type=text],input[type=number]{{width:100%;padding:13px 14px;border:1.5px solid #ddd;border-radius:10px;font-size:1rem;outline:none;transition:border-color .2s;-webkit-appearance:none}}
  input:focus{{border-color:#4CAF50}}
  .section-title{{font-size:.95rem;font-weight:700;color:#444;margin:24px 0 12px;padding-top:20px;border-top:1px solid #eee}}
  .options{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
  .opt input{{display:none}}
  .opt label{{display:flex;align-items:center;justify-content:center;text-align:center;padding:13px 8px;border:1.5px solid #ddd;border-radius:10px;cursor:pointer;font-size:.87rem;font-weight:500;transition:all .2s;line-height:1.3;min-height:54px}}
  .opt input:checked+label{{border-color:#4CAF50;background:#f0faf0;color:#2e7d32;font-weight:700}}
  .error-banner{{background:#fdecea;color:#c62828;border-radius:10px;padding:12px 14px;font-size:.88rem;margin-bottom:18px}}
  button[type=submit]{{width:100%;padding:15px;background:#4CAF50;color:#fff;border:none;border-radius:12px;font-size:1.05rem;font-weight:700;cursor:pointer;margin-top:10px;-webkit-appearance:none}}
  button:active{{background:#43a047}}
</style>
</head>
<body>
<div class="card">
  <h1>🥗 Tu perfil nutricional</h1>
  <p class="subtitle">Completá estos datos y te armo un plan personalizado al toque 😊</p>
  {error_banner}
  <form method="POST">
    <div class="field">
      <label class="field-label" for="name">¿Cómo te llamás?</label>
      <input type="text" id="name" name="name" placeholder="Tu nombre" required autocomplete="given-name" value="{name}">
    </div>
    <div class="field">
      <label class="field-label" for="age">Edad (años)</label>
      <input type="number" id="age" name="age" placeholder="Ej: 28" min="10" max="120" required value="{age}">
    </div>
    <div class="field">
      <label class="field-label" for="weight">Peso (kg)</label>
      <input type="number" id="weight" name="weight" placeholder="Ej: 72" min="20" max="500" step="0.1" required value="{weight}">
    </div>
    <div class="field">
      <label class="field-label" for="height">Altura (cm)</label>
      <input type="number" id="height" name="height" placeholder="Ej: 170" min="100" max="250" step="0.1" required value="{height}">
    </div>

    <p class="section-title">¿Cuál es tu objetivo?</p>
    <div class="options field">
      <div class="opt"><input type="radio" name="goal" id="g1" value="lose_weight" {g_lose_weight} required><label for="g1">⬇️ Bajar de peso</label></div>
      <div class="opt"><input type="radio" name="goal" id="g2" value="gain_muscle" {g_gain_muscle}><label for="g2">💪 Ganar músculo</label></div>
      <div class="opt"><input type="radio" name="goal" id="g3" value="maintain" {g_maintain}><label for="g3">⚖️ Mantenerme</label></div>
      <div class="opt"><input type="radio" name="goal" id="g4" value="eat_healthier" {g_eat_healthier}><label for="g4">🥗 Comer más sano</label></div>
    </div>

    <p class="section-title">Nivel de actividad física</p>
    <div class="options field">
      <div class="opt"><input type="radio" name="activity" id="a1" value="sedentary" {a_sedentary} required><label for="a1">🪑 Sedentario</label></div>
      <div class="opt"><input type="radio" name="activity" id="a2" value="lightly_active" {a_lightly_active}><label for="a2">🚶 Poco activo</label></div>
      <div class="opt"><input type="radio" name="activity" id="a3" value="active" {a_active}><label for="a3">🏃 Activo</label></div>
      <div class="opt"><input type="radio" name="activity" id="a4" value="very_active" {a_very_active}><label for="a4">🔥 Muy activo</label></div>
    </div>

    <button type="submit">Empezar 🚀</button>
  </form>
</div>
</body>
</html>
"""

_SUCCESS_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NutriBot — ¡Listo!</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px}}
  .card{{background:#fff;border-radius:18px;padding:44px 28px;text-align:center;max-width:360px;width:100%;box-shadow:0 2px 16px rgba(0,0,0,.09)}}
  .icon{{font-size:3.2rem;margin-bottom:16px}}
  h1{{font-size:1.4rem;margin-bottom:10px}}
  p{{color:#666;font-size:.95rem;line-height:1.55}}
</style>
</head>
<body>
<div class="card">
  <div class="icon">🎉</div>
  <h1>¡Todo listo, {name}!</h1>
  <p>Tu perfil fue guardado. Volvé a Telegram — ya te envié tu plan personalizado 🥗</p>
</div>
</body>
</html>
"""

_INVALID_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NutriBot — Link inválido</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px}}
  .card{{background:#fff;border-radius:18px;padding:40px 28px;text-align:center;max-width:360px;width:100%;box-shadow:0 2px 16px rgba(0,0,0,.09)}}
  .icon{{font-size:3rem;margin-bottom:16px}}
  h1{{font-size:1.3rem;margin-bottom:10px}}
  p{{color:#666;font-size:.93rem;line-height:1.5}}
</style>
</head>
<body>
<div class="card">
  <div class="icon">🔗</div>
  <h1>Link inválido o expirado</h1>
  <p>Este link ya fue usado o no es válido. Escribí /start en Telegram para obtener uno nuevo.</p>
</div>
</body>
</html>
"""


def _render_form(error: str = "", data: dict = None):
    d = data or {}
    def checked(field, value):
        return "checked" if d.get(field) == value else ""
    return _FORM_HTML.format(
        error_banner=f'<div class="error-banner">⚠️ {error}</div>' if error else "",
        name=d.get("name", ""),
        age=d.get("age", ""),
        weight=d.get("weight", ""),
        height=d.get("height", ""),
        g_lose_weight=checked("goal", "lose_weight"),
        g_gain_muscle=checked("goal", "gain_muscle"),
        g_maintain=checked("goal", "maintain"),
        g_eat_healthier=checked("goal", "eat_healthier"),
        a_sedentary=checked("activity", "sedentary"),
        a_lightly_active=checked("activity", "lightly_active"),
        a_active=checked("activity", "active"),
        a_very_active=checked("activity", "very_active"),
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _get_form(request: web.Request) -> web.Response:
    token = request.match_info["token"]
    if not db.get_telegram_id_by_token(token):
        return web.Response(text=_INVALID_HTML, content_type="text/html", status=404)
    return web.Response(text=_render_form(), content_type="text/html")


async def _post_form(request: web.Request) -> web.Response:
    token = request.match_info["token"]
    telegram_id = db.get_telegram_id_by_token(token)
    if not telegram_id:
        return web.Response(text=_INVALID_HTML, content_type="text/html", status=404)

    raw = await request.post()
    data = {k: raw.get(k, "").strip() for k in ("name", "age", "weight", "height", "goal", "activity")}

    # Validate
    error = _validate(data)
    if error:
        return web.Response(text=_render_form(error, data), content_type="text/html", status=400)

    name = data["name"]
    age = int(data["age"])
    weight = float(data["weight"].replace(",", "."))
    height = float(data["height"].replace(",", "."))
    goal = data["goal"]
    activity = data["activity"]

    db.upsert_user(
        telegram_id,
        name=name, age=age, weight_kg=weight, height_cm=height,
        goal=goal, activity_level=activity, onboarding_complete=1,
    )
    db.delete_onboarding_token(token)

    bot = request.app["bot"]
    user = db.get_user(telegram_id)

    try:
        welcome = await ai.onboarding_welcome(name)
        await bot.send_message(chat_id=telegram_id, text=welcome)
        await bot.send_message(chat_id=telegram_id, text="Armando tu plan personalizado... 🥗")
        plan = await ai.generate_meal_plan(user)
        await bot.send_message(chat_id=telegram_id, text=plan)
        await bot.send_message(
            chat_id=telegram_id,
            text="¡Listo! Ahora podés mandarme fotos de tus comidas o describirme qué estás comiendo 📸",
        )
    except Exception as e:
        logger.error(f"[web] Error sending Telegram messages to {telegram_id}: {e}")

    return web.Response(
        text=_SUCCESS_HTML.format(name=name),
        content_type="text/html",
    )


def _validate(data: dict) -> str:
    if not data["name"]:
        return "Por favor ingresá tu nombre."
    try:
        age = int(data["age"])
        if not (10 <= age <= 120):
            raise ValueError
    except ValueError:
        return "Ingresá una edad válida (entre 10 y 120)."
    try:
        w = float(data["weight"].replace(",", "."))
        if not (20 <= w <= 500):
            raise ValueError
    except ValueError:
        return "Ingresá un peso válido en kg (entre 20 y 500)."
    try:
        h = float(data["height"].replace(",", "."))
        if not (100 <= h <= 250):
            raise ValueError
    except ValueError:
        return "Ingresá una altura válida en cm (entre 100 y 250)."
    if data["goal"] not in VALID_GOALS:
        return "Seleccioná un objetivo."
    if data["activity"] not in VALID_ACTIVITIES:
        return "Seleccioná tu nivel de actividad."
    return ""


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_web_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/onboarding/{token}", _get_form)
    app.router.add_post("/onboarding/{token}", _post_form)
    return app
