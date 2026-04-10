import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from twilio.twiml.messaging_response import MessagingResponse
import pytz
import uvicorn

import db
import payments
from whatsapp_handler import handle_message

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()

    import scheduler
    sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    frm   = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    scheduler.start_scheduler_twilio(sid, token, frm)

    yield

    scheduler.stop_scheduler()


app = FastAPI(lifespan=lifespan)


@app.get("/onboarding", response_class=HTMLResponse)
def onboarding():
    with open("onboarding.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/onboarding/complete")
async def onboarding_complete(request: Request):
    data = await request.json()
    phone = db.normalize_phone(data.get("phone") or "")
    if not phone:
        return {"ok": False, "error": "no phone"}

    logger.info(f"[onboarding/complete] phone={phone}, data={data}")

    # Look up existing user by phone first (bot already created them)
    existing = db.get_user_by_phone(phone)
    logger.info(f"[onboarding/complete] existing user={existing}")

    if existing:
        tid = existing["telegram_id"]
    else:
        # Fallback: derive tid from phone (same as whatsapp_handler)
        tid = int(hashlib.sha256(phone.encode()).hexdigest(), 16) % (2**31 - 1) + 1

    # Normalize coach_mode: webapp sends "challenger" but bot uses "roaster"
    coach_mode = data.get("coach_mode", "mentor")
    if coach_mode == "challenger":
        coach_mode = "roaster"

    db.upsert_user(
        tid,
        phone=phone,
        name=data.get("name"),
        age=int(data.get("age", 0)) or None,
        weight_kg=float(data.get("weight", 0)) or None,
        height_cm=float(data.get("height", 0)) or None,
        goal=data.get("goal"),
        activity_level=data.get("activity"),
        coach_mode=coach_mode,
        onboarding_complete=1,
        onboarding_step="done",
    )

    updated = db.get_user_by_phone(phone)
    logger.info(f"[onboarding/complete] updated user={updated}")

    # Card-first: user must enter card before getting access
    db.create_pending_subscription(tid)
    logger.info(f"[onboarding/complete] pending_payment subscription created for tid={tid}")

    return {"ok": True}


@app.post("/webhook")
async def webhook(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    numero = db.normalize_phone(From.replace("whatsapp:", ""))
    has_media = int(NumMedia) > 0
    reply = await handle_message(numero, Body, MediaUrl0 if has_media else None)
    resp = MessagingResponse()
    resp.message(reply)
    return Response(content=str(resp), media_type="application/xml; charset=utf-8")


@app.post("/webhook/mercadopago")
async def mp_webhook(request: Request):
    """Receive MercadoPago IPN notifications."""
    try:
        data = await request.json()
        logger.info(f"[mp_webhook] received: {data}")
        payments.handle_webhook(data)
    except Exception as e:
        logger.error(f"[mp_webhook] error: {e}", exc_info=True)
    # Always return 200 so MP doesn't retry
    return {"ok": True}


@app.get("/subscription/payment", response_class=HTMLResponse)
def subscription_payment(phone: str = ""):
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CoachKai — Activar suscripcion</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px}}
  .card{{background:#fff;border-radius:18px;padding:36px 24px;max-width:400px;width:100%;box-shadow:0 2px 16px rgba(0,0,0,.09)}}
  h1{{font-size:1.3rem;margin-bottom:6px;text-align:center}}
  .subtitle{{color:#666;font-size:.9rem;text-align:center;margin-bottom:24px;line-height:1.5}}
  .price{{text-align:center;margin-bottom:20px}}
  .price-amount{{font-size:2rem;font-weight:800;color:#2d9d8f}}
  .price-period{{font-size:.85rem;color:#999}}
  .trial-badge{{display:block;text-align:center;background:#e8f5f3;color:#2d9d8f;font-weight:600;font-size:.88rem;padding:8px;border-radius:8px;margin-bottom:24px}}
  .field{{margin-bottom:16px}}
  label{{display:block;font-size:.85rem;font-weight:600;color:#444;margin-bottom:6px}}
  input[type=email]{{width:100%;padding:13px 14px;border:1.5px solid #ddd;border-radius:10px;font-size:1rem;outline:none;-webkit-appearance:none}}
  input:focus{{border-color:#2d9d8f}}
  button{{width:100%;padding:15px;background:#2d9d8f;color:#fff;border:none;border-radius:12px;font-size:1.05rem;font-weight:700;cursor:pointer;margin-top:8px;-webkit-appearance:none}}
  button:active{{background:#258a7e}}
  button:disabled{{opacity:.6;cursor:not-allowed}}
  .error{{color:#c62828;font-size:.85rem;margin-top:10px;text-align:center;display:none}}
  .note{{color:#999;font-size:.78rem;text-align:center;margin-top:16px;line-height:1.4}}
</style>
</head>
<body>
<div class="card">
  <h1>Activa CoachKai</h1>
  <p class="subtitle">Seguimiento nutricional con IA, todos los dias en tu WhatsApp.</p>
  <div class="price">
    <div class="price-amount">$9.999</div>
    <div class="price-period">por mes</div>
  </div>
  <div class="trial-badge">Los primeros 7 dias son gratis</div>
  <form id="payForm" onsubmit="return handleSubmit(event)">
    <div class="field">
      <label for="email">Tu email (para el recibo de pago)</label>
      <input type="email" id="email" name="email" placeholder="tu@email.com" required>
    </div>
    <button type="submit" id="submitBtn">Activar suscripcion</button>
    <div class="error" id="error"></div>
  </form>
  <p class="note">Se te va a debitar automaticamente cada mes. Podes cancelar cuando quieras desde WhatsApp.</p>
</div>
<script>
var phone = '{phone}';
function handleSubmit(e) {{
  e.preventDefault();
  var btn = document.getElementById('submitBtn');
  var errEl = document.getElementById('error');
  var email = document.getElementById('email').value.trim();
  if (!email) return;
  btn.disabled = true;
  btn.textContent = 'Redirigiendo...';
  errEl.style.display = 'none';
  fetch('/api/subscription/checkout?phone=' + encodeURIComponent(phone) + '&email=' + encodeURIComponent(email))
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (data.ok && data.checkout_url) {{
        window.location.href = data.checkout_url;
      }} else {{
        errEl.textContent = 'No se pudo crear el checkout. Intenta de nuevo.';
        errEl.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Activar suscripcion';
      }}
    }})
    .catch(function() {{
      errEl.textContent = 'Error de conexion. Intenta de nuevo.';
      errEl.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Activar suscripcion';
    }});
  return false;
}}
</script>
</body>
</html>""")


@app.get("/subscription/success", response_class=HTMLResponse)
def subscription_success(tid: str = ""):
    return HTMLResponse("""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CoachKai — Suscripcion activa</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px}
  .card{background:#fff;border-radius:18px;padding:44px 28px;text-align:center;max-width:360px;width:100%;box-shadow:0 2px 16px rgba(0,0,0,.09)}
  .icon{font-size:3.2rem;margin-bottom:16px}
  h1{font-size:1.4rem;margin-bottom:10px}
  p{color:#666;font-size:.95rem;line-height:1.55}
</style>
</head>
<body>
<div class="card">
  <div class="icon">🎉</div>
  <h1>Suscripcion activada!</h1>
  <p>Tu pago fue procesado correctamente. Volve a WhatsApp y segui usando CoachKai sin limites.</p>
</div>
</body>
</html>""")


@app.get("/api/subscription/checkout")
async def subscription_checkout(phone: str = "", email: str = ""):
    """Generate a MercadoPago checkout URL for a user."""
    phone = db.normalize_phone(phone)
    if not phone or not email:
        return {"ok": False, "error": "phone and email required"}
    user = db.get_user_by_phone(phone)
    if not user:
        return {"ok": False, "error": "user not found"}
    tid = user["telegram_id"]
    url = payments.get_checkout_url(tid, email)
    if url:
        return {"ok": True, "checkout_url": url}
    return {"ok": False, "error": "could not create checkout"}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

_BA = pytz.timezone("America/Argentina/Buenos_Aires")


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
var TOKEN = '__TOKEN__';
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
  fetch('/api/nutrition/' + TG_ID + '?date=' + dateStr + '&token=' + TOKEN)
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

_FORBIDDEN_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CoachKai \u2014 Acceso denegado</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f4f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px}
  .card{background:#fff;border-radius:18px;padding:40px 28px;text-align:center;max-width:360px;width:100%;box-shadow:0 2px 16px rgba(0,0,0,.09)}
  .icon{font-size:3rem;margin-bottom:16px}
  h1{font-size:1.3rem;margin-bottom:10px}
  p{color:#666;font-size:.93rem;line-height:1.5}
</style>
</head>
<body>
<div class="card">
  <div class="icon">\U0001f512</div>
  <h1>Acceso denegado</h1>
  <p>Token inv\u00e1lido o faltante. Solicit\u00e1 el link desde WhatsApp con /dashboard.</p>
</div>
</body>
</html>
"""


@app.get("/dashboard/{telegram_id}", response_class=HTMLResponse)
def dashboard_page(telegram_id: int, token: str = ""):
    expected_token = db.get_or_create_dashboard_token(telegram_id)
    if not token or token != expected_token:
        return HTMLResponse(_FORBIDDEN_HTML, status_code=403)
    html = _DASHBOARD_HTML.replace("__TELEGRAM_ID__", str(telegram_id)).replace("__TOKEN__", token)
    return HTMLResponse(html)


@app.get("/api/nutrition/{telegram_id}")
def api_nutrition(telegram_id: int, token: str = "", date: str = ""):
    expected_token = db.get_or_create_dashboard_token(telegram_id)
    if not token or token != expected_token:
        return JSONResponse({"error": "forbidden"}, status_code=403)

    if not date:
        date = datetime.now(_BA).strftime("%Y-%m-%d")

    user = db.get_user(telegram_id)
    if not user:
        return JSONResponse({"error": "user not found"}, status_code=404)

    meals = _get_meals_for_date(telegram_id, date)

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

    return {
        "user": {"name": user.get("name", ""), "daily_calories": daily_calories},
        "totals": totals,
        "meals": formatted_meals,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
