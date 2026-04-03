import hashlib
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from twilio.twiml.messaging_response import MessagingResponse
import uvicorn

import db
from whatsapp_handler import handle_message


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
    phone = (data.get("phone") or "").replace("+", "").replace(" ", "").replace("-", "")
    if not phone:
        return {"ok": False, "error": "no phone"}

    # Look up existing user by phone first (bot already created them)
    existing = db.get_user_by_phone(phone)
    if existing:
        tid = existing["telegram_id"]
    else:
        # Fallback: derive tid from phone (same as whatsapp_handler)
        tid = int(hashlib.sha256(phone.encode()).hexdigest(), 16) % (2**31 - 1) + 1

    db.upsert_user(
        tid,
        phone=phone,
        name=data.get("name"),
        age=int(data.get("age", 0)) or None,
        weight_kg=float(data.get("weight", 0)) or None,
        height_cm=float(data.get("height", 0)) or None,
        goal=data.get("goal"),
        activity_level=data.get("activity"),
        coach_mode=data.get("coach_mode", "mentor"),
        onboarding_complete=1,
        onboarding_step="done",
    )
    return {"ok": True}


@app.post("/webhook")
async def webhook(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    numero = From.replace("whatsapp:", "")
    has_media = int(NumMedia) > 0
    reply = await handle_message(numero, Body, MediaUrl0 if has_media else None)
    resp = MessagingResponse()
    resp.message(reply)
    return Response(content=str(resp), media_type="application/xml")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
