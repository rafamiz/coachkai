import hashlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from twilio.twiml.messaging_response import MessagingResponse
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

    # Create 7-day free trial
    db.create_trial(tid)
    logger.info(f"[onboarding/complete] trial created for tid={tid}")

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
    return Response(content=str(resp), media_type="application/xml")


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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
