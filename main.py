import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form
from fastapi.responses import Response
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


@app.get("/health")
def health():
    return {"status": "ok"}


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
