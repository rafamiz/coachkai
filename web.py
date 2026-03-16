import json
import logging
from datetime import datetime

import pytz
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
# Dashboard
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coach Kai</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f7f6;color:#222;padding:0 0 48px}
  .container{max-width:480px;margin:0 auto;padding:0 14px}
  header{display:flex;align-items:center;justify-content:space-between;padding:18px 0 10px}
  .logo{font-size:1.2rem;font-weight:800;color:#2d9d8f;letter-spacing:-.3px}
  .header-right{text-align:right}
  .user-name{font-size:.95rem;font-weight:600;color:#333}
  .date-label{font-size:.78rem;color:#999;margin-top:2px}
  .card{background:#fff;border-radius:16px;padding:18px;box-shadow:0 2px 12px rgba(0,0,0,.07);margin-bottom:12px}
  .card-title{font-size:.72rem;font-weight:700;color:#aaa;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
  .calorie-section{display:flex;align-items:center;gap:20px}
  .ring-wrap{position:relative;width:116px;height:116px;flex-shrink:0}
  .ring-wrap svg{transform:rotate(-90deg)}
  .ring-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;pointer-events:none}
  .ring-cal{font-size:1.55rem;font-weight:800;color:#2d9d8f;line-height:1}
  .ring-unit{font-size:.65rem;color:#aaa;margin-top:3px}
  .calorie-info{flex:1}
  .cal-stat{margin-bottom:10px}
  .cal-stat:last-child{margin-bottom:0}
  .cal-stat-label{font-size:.72rem;color:#aaa;margin-bottom:1px}
  .cal-stat-val{font-size:1.05rem;font-weight:700;color:#333}
  .cal-remaining{color:#2d9d8f}
  .macro-item{margin-bottom:13px}
  .macro-item:last-child{margin-bottom:0}
  .macro-header{display:flex;justify-content:space-between;margin-bottom:5px}
  .macro-name{font-size:.82rem;font-weight:600;color:#555}
  .macro-val{font-size:.82rem;color:#999}
  .bar-track{background:#f2f2f2;border-radius:5px;height:8px;overflow:hidden}
  .bar-fill{height:100%;border-radius:5px;transition:width .5s ease}
  .bar-protein{background:#4CAF82}
  .bar-carbs{background:#2d9d8f}
  .bar-fats{background:#f0a030}
  .meal-group-title{font-size:.82rem;font-weight:700;color:#2d9d8f;margin-bottom:8px}
  .meal-item{display:flex;align-items:flex-start;padding:9px 0;border-bottom:1px solid #f5f5f5}
  .meal-item:last-child{border-bottom:none}
  .meal-time{font-size:.72rem;color:#bbb;width:38px;flex-shrink:0;padding-top:2px}
  .meal-desc{flex:1;font-size:.86rem;color:#333;line-height:1.4}
  .meal-cal{font-size:.82rem;font-weight:600;color:#777;white-space:nowrap;margin-left:8px}
  .date-nav{display:flex;gap:10px;margin-top:4px}
  .date-btn{flex:1;padding:13px;border:none;border-radius:12px;font-size:.9rem;font-weight:600;cursor:pointer;-webkit-appearance:none;transition:opacity .15s}
  .date-btn:active{opacity:.75}
  .date-btn-sec{background:#e8f5f3;color:#2d9d8f}
  .date-btn-pri{background:#2d9d8f;color:#fff}
  .empty{text-align:center;padding:28px 0;color:#bbb;font-size:.88rem}
  .loading{text-align:center;padding:40px 0;color:#ccc;font-size:.88rem}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">Coach Kai</div>
    <div class="header-right">
      <div class="user-name" id="user-name">&nbsp;</div>
      <div class="date-label" id="date-label">&nbsp;</div>
    </div>
  </header>

  <div class="card">
    <div class="card-title">Calor\u00edas</div>
    <div class="calorie-section">
      <div class="ring-wrap">
        <svg width="116" height="116" viewBox="0 0 116 116">
          <circle cx="58" cy="58" r="48" fill="none" stroke="#eee" stroke-width="10"/>
          <circle id="ring-circle" cx="58" cy="58" r="48" fill="none"
            stroke="#2d9d8f" stroke-width="10"
            stroke-dasharray="301.6" stroke-dashoffset="301.6"
            stroke-linecap="round"/>
        </svg>
        <div class="ring-center">
          <div class="ring-cal" id="ring-cal">0</div>
          <div class="ring-unit">kcal</div>
        </div>
      </div>
      <div class="calorie-info">
        <div class="cal-stat">
          <div class="cal-stat-label">Objetivo</div>
          <div class="cal-stat-val" id="goal-cal">&mdash;</div>
        </div>
        <div class="cal-stat">
          <div class="cal-stat-label">Restante</div>
          <div class="cal-stat-val cal-remaining" id="remaining-cal">&mdash;</div>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Macronutrientes</div>
    <div class="macro-item">
      <div class="macro-header">
        <span class="macro-name">Prote\u00ednas</span>
        <span class="macro-val" id="protein-val">0g</span>
      </div>
      <div class="bar-track"><div class="bar-fill bar-protein" id="protein-bar" style="width:0%"></div></div>
    </div>
    <div class="macro-item">
      <div class="macro-header">
        <span class="macro-name">Carbohidratos</span>
        <span class="macro-val" id="carbs-val">0g</span>
      </div>
      <div class="bar-track"><div class="bar-fill bar-carbs" id="carbs-bar" style="width:0%"></div></div>
    </div>
    <div class="macro-item">
      <div class="macro-header">
        <span class="macro-name">Grasas</span>
        <span class="macro-val" id="fats-val">0g</span>
      </div>
      <div class="bar-track"><div class="bar-fill bar-fats" id="fats-bar" style="width:0%"></div></div>
    </div>
  </div>

  <div id="meals-container"><div class="loading">Cargando...</div></div>

  <div class="date-nav">
    <button class="date-btn date-btn-sec" onclick="changeDate(-1)">\u2190 Ayer</button>
    <button class="date-btn date-btn-pri" onclick="goToday()">Hoy</button>
  </div>
</div>
<script>
var TG_ID = '__TELEGRAM_ID__';
var currentDate = new Date();

function fmtDate(d) {
  var y = d.getFullYear();
  var m = String(d.getMonth()+1).padStart(2,'0');
  var day = String(d.getDate()).padStart(2,'0');
  return y + '-' + m + '-' + day;
}

function fmtDateDisplay(d) {
  var days = ['Domingo','Lunes','Martes','Mi\u00e9rcoles','Jueves','Viernes','S\u00e1bado'];
  var months = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
  var today = new Date();
  var yesterday = new Date(today); yesterday.setDate(today.getDate()-1);
  if (fmtDate(d) === fmtDate(today)) return 'Hoy, ' + d.getDate() + ' de ' + months[d.getMonth()];
  if (fmtDate(d) === fmtDate(yesterday)) return 'Ayer, ' + d.getDate() + ' de ' + months[d.getMonth()];
  return days[d.getDay()] + ' ' + d.getDate() + ' de ' + months[d.getMonth()];
}

var MEAL_LABELS = {
  breakfast:'Desayuno', desayuno:'Desayuno',
  lunch:'Almuerzo', almuerzo:'Almuerzo',
  snack:'Merienda', merienda:'Merienda',
  dinner:'Cena', cena:'Cena'
};
var MEAL_ORDER = ['breakfast','desayuno','lunch','almuerzo','snack','merienda','dinner','cena'];

function loadData() {
  var dateStr = fmtDate(currentDate);
  document.getElementById('date-label').textContent = fmtDateDisplay(currentDate);
  fetch('/api/nutrition/' + TG_ID + '?date=' + dateStr)
    .then(function(r){ return r.json(); })
    .then(function(data){ render(data); })
    .catch(function(){
      document.getElementById('meals-container').innerHTML =
        '<div class="card"><div class="empty">Error al cargar datos</div></div>';
    });
}

function render(data) {
  var user = data.user || {};
  var totals = data.totals || {};
  var meals = data.meals || [];

  document.getElementById('user-name').textContent = user.name || '';

  var consumed = Math.round(totals.calories || 0);
  var goal = user.daily_calories || 2000;
  var remaining = Math.max(0, goal - consumed);
  var pct = Math.min(1, consumed / goal);
  var circ = 301.6;

  document.getElementById('ring-cal').textContent = consumed;
  document.getElementById('ring-circle').style.strokeDashoffset = (circ * (1 - pct)).toFixed(1);
  document.getElementById('goal-cal').textContent = goal + ' kcal';
  document.getElementById('remaining-cal').textContent = remaining + ' kcal';

  var proteinGoal = Math.max(1, Math.round(goal * 0.30 / 4));
  var carbsGoal = Math.max(1, Math.round(goal * 0.45 / 4));
  var fatsGoal = Math.max(1, Math.round(goal * 0.25 / 9));

  var proteins = Math.round(totals.proteins_g || 0);
  var carbs = Math.round(totals.carbs_g || 0);
  var fats = Math.round(totals.fats_g || 0);

  document.getElementById('protein-val').textContent = proteins + 'g';
  document.getElementById('carbs-val').textContent = carbs + 'g';
  document.getElementById('fats-val').textContent = fats + 'g';
  document.getElementById('protein-bar').style.width = Math.min(100, proteins/proteinGoal*100).toFixed(1) + '%';
  document.getElementById('carbs-bar').style.width = Math.min(100, carbs/carbsGoal*100).toFixed(1) + '%';
  document.getElementById('fats-bar').style.width = Math.min(100, fats/fatsGoal*100).toFixed(1) + '%';

  var groups = {};
  meals.forEach(function(m) {
    var type = (m.meal_type || 'other').toLowerCase();
    if (!groups[type]) groups[type] = [];
    groups[type].push(m);
  });

  var ordered = MEAL_ORDER.filter(function(k){ return groups[k]; });
  var other = Object.keys(groups).filter(function(k){ return MEAL_ORDER.indexOf(k) === -1; });
  var seen = {};
  var keys = ordered.concat(other).filter(function(k){ return seen[k] ? false : (seen[k]=true); });

  var html = '';
  if (keys.length === 0) {
    html = '<div class="card"><div class="empty">Sin comidas registradas</div></div>';
  } else {
    keys.forEach(function(type) {
      var label = MEAL_LABELS[type] || (type.charAt(0).toUpperCase() + type.slice(1));
      var items = groups[type];
      var groupCal = items.reduce(function(s,m){ return s + (m.calories_est||0); }, 0);
      html += '<div class="card">';
      html += '<div class="meal-group-title">' + label + ' &bull; ' + groupCal + ' kcal</div>';
      items.forEach(function(m) {
        html += '<div class="meal-item">';
        html += '<div class="meal-time">' + (m.eaten_at||'') + '</div>';
        html += '<div class="meal-desc">' + (m.description||'') + '</div>';
        html += '<div class="meal-cal">' + (m.calories_est||0) + ' kcal</div>';
        html += '</div>';
      });
      html += '</div>';
    });
  }
  document.getElementById('meals-container').innerHTML = html;
}

function changeDate(delta) {
  var d = new Date(currentDate);
  d.setDate(d.getDate() + delta);
  currentDate = d;
  loadData();
}

function goToday() {
  currentDate = new Date();
  loadData();
}

loadData();
setInterval(loadData, 5 * 60 * 1000);
</script>
</body>
</html>
"""


def _calc_tdee(user: dict) -> int:
    weight = user.get("weight_kg") or 70
    height = user.get("height_cm") or 170
    age = user.get("age") or 30
    goal = user.get("goal") or "maintain"
    activity = user.get("activity_level") or "sedentary"
    bmr = 10 * weight + 6.25 * height - 5 * age + 5
    mult = {"sedentary": 1.2, "lightly_active": 1.375, "active": 1.55, "very_active": 1.725}.get(activity, 1.2)
    tdee = bmr * mult
    if goal == "lose_weight":
        tdee *= 0.85
    elif goal == "gain_muscle":
        tdee *= 1.1
    return int(tdee)


def _get_meals_for_date(telegram_id: int, date_str: str) -> list:
    conn = db.get_conn()
    c = db._cur(conn)
    if db._USE_POSTGRES:
        c.execute(
            db._q("SELECT * FROM meals WHERE telegram_id = ? AND DATE(eaten_at) = ? ORDER BY eaten_at ASC"),
            (telegram_id, date_str),
        )
    else:
        c.execute(
            db._q("SELECT * FROM meals WHERE telegram_id = ? AND eaten_at LIKE ? ORDER BY eaten_at ASC"),
            (telegram_id, f"{date_str}%"),
        )
    rows = c.fetchall()
    db._release(conn)
    return db._rows(rows)


async def _api_nutrition(request: web.Request) -> web.Response:
    try:
        telegram_id = int(request.match_info["telegram_id"])
    except (ValueError, KeyError):
        return web.Response(text='{"error":"invalid id"}', content_type="application/json", status=400)

    date_str = request.rel_url.query.get("date", "")
    if not date_str:
        _BA = pytz.timezone("America/Argentina/Buenos_Aires")
        date_str = datetime.now(_BA).strftime("%Y-%m-%d")

    user = db.get_user(telegram_id)
    if not user:
        return web.Response(text='{"error":"user not found"}', content_type="application/json", status=404)

    meals = _get_meals_for_date(telegram_id, date_str)

    totals = {
        "calories": sum(m.get("calories_est") or 0 for m in meals),
        "proteins_g": round(sum(m.get("proteins_g") or 0 for m in meals), 1),
        "carbs_g": round(sum(m.get("carbs_g") or 0 for m in meals), 1),
        "fats_g": round(sum(m.get("fats_g") or 0 for m in meals), 1),
    }

    formatted_meals = []
    for m in meals:
        eaten_at = m.get("eaten_at", "") or ""
        time_str = eaten_at[11:16] if len(eaten_at) >= 16 else ""
        formatted_meals.append({
            "description": m.get("description", ""),
            "calories_est": m.get("calories_est") or 0,
            "meal_type": m.get("meal_type", ""),
            "eaten_at": time_str,
            "proteins_g": m.get("proteins_g") or 0,
            "carbs_g": m.get("carbs_g") or 0,
            "fats_g": m.get("fats_g") or 0,
        })

    daily_calories = user.get("daily_calories") or _calc_tdee(user)

    result = {
        "user": {"name": user.get("name", ""), "daily_calories": daily_calories},
        "totals": totals,
        "meals": formatted_meals,
    }
    return web.Response(
        text=json.dumps(result, ensure_ascii=False),
        content_type="application/json",
    )


async def _get_dashboard(request: web.Request) -> web.Response:
    try:
        telegram_id = int(request.match_info["telegram_id"])
    except (ValueError, KeyError):
        return web.Response(text="Invalid ID", status=400)

    html = _DASHBOARD_HTML.replace("__TELEGRAM_ID__", str(telegram_id))
    return web.Response(text=html, content_type="text/html")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_web_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/onboarding/{token}", _get_form)
    app.router.add_post("/onboarding/{token}", _post_form)
    app.router.add_get("/dashboard/{telegram_id}", _get_dashboard)
    app.router.add_get("/api/nutrition/{telegram_id}", _api_nutrition)
    return app
