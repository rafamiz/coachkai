# NutriBot — Port a Twilio WhatsApp

## Goal
Replace the Telegram bot with a WhatsApp bot via Twilio, keeping all the AI/DB logic intact.
This will replace Telabot at the same Twilio sandbox number.

## Architecture
- FastAPI app with /webhook endpoint (same as Telabot)
- Twilio sends POST to /webhook on every incoming message
- Photos come as MediaUrl0 in Twilio payload (download and analyze with Claude Vision)
- Session state stored in DB (no in-memory context like Telegram)
- Deploy on Railway, update Twilio sandbox webhook URL

## Twilio credentials
TWILIO_ACCOUNT_SID=ACaa11a4f4b4b3c813d73489ccb64c5f8c
TWILIO_AUTH_TOKEN=AYRKGJE5KXWC8CY31VNBHK7U
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
ANTHROPIC_API_KEY=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

## New files to create

### main.py (entry point, replaces bot.py)
```python
from fastapi import FastAPI, Form, Request
from twilio.twiml.messaging_response import MessagingResponse
import uvicorn, os

app = FastAPI()

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/webhook")
async def webhook(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    numero = From.replace("whatsapp:", "")
    resp = MessagingResponse()
    reply = await handle_message(numero, Body, MediaUrl0 if int(NumMedia) > 0 else None)
    resp.message(reply)
    return Response(content=str(resp), media_type="application/xml")
```

### whatsapp_handler.py (core logic, replaces handlers.py)
- get_or_create_user(numero) — find user by phone number
- handle_message(numero, text, media_url) — main dispatch
- Onboarding state machine stored in users table (new column: onboarding_step TEXT)
- Commands: /start, /stats, /plan, /coach, /reset (detect by text starting with /)
- If media_url → download image → analyze_meal_photo()
- Else → analyze_meal_text() or handle onboarding step

### Onboarding via WhatsApp
Replace Telegram inline buttons with numbered responses:
```
"¿Cuál es tu objetivo?
1️⃣ Bajar de peso
2️⃣ Ganar músculo  
3️⃣ Mantenerme"
```
User replies "1", "2", or "3"

For coach mode:
```
"¿Qué tipo de coach querés?
1️⃣ 🤝 Mentor — Te apoyo con cariño
2️⃣ 🔥 Roaster — Sin filtro, te digo todo"
```

## DB changes needed
- users table: use `phone` column instead of `telegram_id`, add `onboarding_step` column
- Or: add `phone` column and `onboarding_step` to existing users table
- Keep all other tables (meals, followups, eating_schedule) as-is

## Scheduler
- Keep APScheduler for daily summary at 21:30 and macro nudge at 19:00
- Send via Twilio REST API instead of Telegram:
```python
from twilio.rest import Client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
client.messages.create(
    from_='whatsapp:+14155238886',
    to=f'whatsapp:{phone}',
    body=message
)
```

## Photo handling
```python
import httpx, base64
async def download_media(url):
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    async with httpx.AsyncClient() as c:
        r = await c.get(url, auth=auth)
        return base64.b64encode(r.content).decode()
# Then pass base64 to Claude vision
```

## Procfile
```
web: uvicorn main:app --host 0.0.0.0 --port 8000
```

## Requirements additions
```
twilio
fastapi
uvicorn
httpx
```

## After building
1. Test locally: uvicorn main:app --port 8001
2. git add -A && git commit -m "feat: port nutribot to twilio whatsapp"
3. git push (deploys to Railway automatically)
4. Update Twilio sandbox webhook: https://nutribot-production.up.railway.app/webhook
5. openclaw system event --text "Done: NutriBot portado a Twilio WhatsApp. Webhook listo para actualizar en Twilio." --mode now

## Note
- Keep bot.py and handlers.py for Telegram (don't delete) — rename to bot_telegram.py
- New entry point is main.py
- python not python3
- Port 8000 hardcoded in Procfile (Railway expects this)
