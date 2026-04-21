"""
Integration tests for CoachKai WhatsApp bot.
Uses httpx.AsyncClient with ASGITransport — no server needed.
Mocks AI calls to test the full request/response + DB persistence pipeline.
"""

import hashlib
import json
import os
import sqlite3
import sys

import pytest
import pytest_asyncio
import httpx

pytestmark = pytest.mark.asyncio

# Force test to use SQLite, no Postgres
os.environ.pop("DATABASE_URL", None)
# Dummy API key so ai.py doesn't complain
os.environ.setdefault("GEMINI_API_KEY", "test-key")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PHONE = "5491199999999"
TEST_DB = "test_nutribot.db"


def _phone_to_tid(phone: str) -> int:
    h = int(hashlib.sha256(phone.encode()).hexdigest(), 16)
    return h % (2**31 - 1) + 1


TID = _phone_to_tid(PHONE)


@pytest.fixture(autouse=True)
def _setup_db(monkeypatch, tmp_path):
    """Use a fresh SQLite DB for every test."""
    db_file = str(tmp_path / "test.db")
    import db
    monkeypatch.setattr(db, "DB_PATH", db_file)
    monkeypatch.setattr(db, "_USE_POSTGRES", False)
    db.init_db()
    yield


@pytest.fixture()
def _onboarded_user():
    """Create a fully onboarded user in the DB."""
    import db
    db.upsert_user(
        TID,
        phone=PHONE,
        name="TestUser",
        age=28,
        weight_kg=75,
        height_cm=175,
        goal="lose_weight",
        activity_level="active",
        coach_mode="mentor",
        onboarding_complete=1,
        onboarding_step="welcomed",
    )


@pytest.fixture()
def _mock_scheduler(monkeypatch):
    """Prevent the scheduler from starting real background jobs."""
    import scheduler
    monkeypatch.setattr(scheduler, "start_scheduler_twilio", lambda *a, **kw: None)
    monkeypatch.setattr(scheduler, "stop_scheduler", lambda *a, **kw: None)


@pytest_asyncio.fixture()
async def client(_mock_scheduler):
    """httpx async client wired to the FastAPI app (no server)."""
    from main import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_process_message(return_value):
    """Return a coroutine that yields *return_value* regardless of input."""
    async def _fake(*args, **kwargs):
        return return_value
    return _fake


def _mock_generate_meal_plan(*args, **kwargs):
    async def _fake(*a, **kw):
        return {
            "calories": 2000,
            "protein_g": 150,
            "carbs_g": 200,
            "fat_g": 70,
            "summary": "Plan personalizado",
            "tips": ["Toma agua"],
            "breakfasts": ["Avena con frutas"],
            "lunches": ["Pollo con arroz"],
            "dinners": ["Ensalada completa"],
            "snacks": ["Yogur"],
        }
    return _fake


async def _send(client: httpx.AsyncClient, text: str, media_url: str = None):
    """Send a simulated WhatsApp message and return response text."""
    data = {
        "From": f"whatsapp:+{PHONE}",
        "Body": text,
        "NumMedia": "1" if media_url else "0",
    }
    if media_url:
        data["MediaUrl0"] = media_url
        data["MediaContentType0"] = "image/jpeg"
    r = await client.post("/webhook", data=data)
    assert r.status_code == 200, f"webhook returned {r.status_code}: {r.text}"
    # Parse TwiML <Body>…</Body>
    import re
    m = re.search(r"<Body>(.*?)</Body>", r.text, re.DOTALL)
    if not m:
        m = re.search(r"<Message>(.*?)</Message>", r.text, re.DOTALL)
    return m.group(1) if m else r.text


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestNewUser:
    async def test_new_user_gets_onboarding(self, client):
        reply = await _send(client, "hola")
        assert "onboarding" in reply.lower() or "perfil" in reply.lower()
        assert "http" in reply.lower() or "coachkai" in reply.lower()


class TestOnboardingAPI:
    async def test_complete_onboarding(self, client):
        # First create the user via webhook so they exist
        await _send(client, "hola")

        data = {
            "phone": PHONE,
            "name": "TestUser",
            "age": 28,
            "weight": 75,
            "height": 175,
            "goal": "lose_weight",
            "activity": "active",
            "coach_mode": "mentor",
        }
        r = await client.post("/api/onboarding/complete", json=data)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True

        # Verify DB
        import db
        user = db.get_user_by_phone(PHONE)
        assert user is not None
        assert user["onboarding_complete"] == 1
        assert user["name"] == "TestUser"
        assert user["goal"] == "lose_weight"


class TestFoodLogging:
    async def test_meal_saved_to_db(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "meal",
            "meal": {
                "detected_food": "pizza",
                "meal_type": "dinner",
                "calories": 800,
                "proteins_g": 35,
                "carbs_g": 90,
                "fats_g": 30,
            },
            "reply": "Pizza registrada. 800 kcal aprox.",
        }))

        reply = await _send(client, "comi una pizza")
        assert "pizza" in reply.lower() or "registrad" in reply.lower() or "800" in reply

        import db
        meals = db.get_today_meals(TID)
        assert len(meals) >= 1
        m = meals[-1]
        assert m["calories_est"] == 800
        assert "pizza" in m["description"].lower()

    async def test_breakfast_with_macros(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "meal",
            "meal": {
                "detected_food": "avena con leche y fruta",
                "meal_type": "breakfast",
                "calories": 350,
                "proteins_g": 12,
                "carbs_g": 55,
                "fats_g": 8,
            },
            "reply": "Desayuno registrado. 350 kcal.",
        }))

        reply = await _send(client, "desayune avena con leche y fruta")
        assert len(reply) > 5

        import db
        meals = db.get_today_meals(TID)
        assert len(meals) >= 1
        m = meals[-1]
        assert m["calories_est"] == 350
        assert m["proteins_g"] == 12
        assert m["carbs_g"] == 55
        assert m["fats_g"] == 8


class TestExerciseLogging:
    async def test_workout_saved_to_db(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "workout",
            "workout": {
                "workout_type": "gym_strength",
                "description": "pecho y triceps",
                "duration_min": 45,
                "calories_burned": 300,
                "intensity": "high",
            },
            "reply": "Entrenamiento registrado. 300 kcal quemadas.",
        }))

        reply = await _send(client, "fui al gym, hice pecho y triceps por 45 minutos")
        assert "registrad" in reply.lower() or "300" in reply

        import db
        workouts = db.get_today_workouts(TID)
        assert len(workouts) >= 1
        w = workouts[-1]
        assert w["workout_type"] == "gym_strength"
        assert w["calories_burned"] == 300

    async def test_cardio_saved(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "workout",
            "workout": {
                "workout_type": "running",
                "description": "corrida 30 min",
                "duration_min": 30,
                "calories_burned": 250,
                "intensity": "moderate",
                "distance_km": 4.5,
            },
            "reply": "Cardio registrado.",
        }))

        await _send(client, "sali a correr 30 minutos")
        import db
        workouts = db.get_today_workouts(TID)
        assert len(workouts) >= 1
        assert workouts[-1]["workout_type"] == "running"


class TestDeleteMeal:
    async def test_delete_removes_from_db(self, client, _onboarded_user, monkeypatch):
        import db

        # Add a meal first
        user = db.get_user(TID)
        db.add_meal(
            user_id=user["id"],
            telegram_id=TID,
            description="hamburguesa",
            photo_path="",
            calories_est=600,
            meal_type="lunch",
            claude_analysis="",
        )
        meals_before = db.get_today_meals(TID)
        meal_id = meals_before[-1]["id"]

        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "delete_meal",
            "meal_ids": [meal_id],
            "reply": "Listo, borré la hamburguesa.",
        }))

        reply = await _send(client, "borra la hamburguesa")
        assert "borr" in reply.lower() or "elimin" in reply.lower() or "listo" in reply.lower()

        meals_after = db.get_today_meals(TID)
        ids_after = [m["id"] for m in meals_after]
        assert meal_id not in ids_after


class TestPastMealLogging:
    async def test_yesterday_meal_has_correct_date(self, client, _onboarded_user, monkeypatch):
        from datetime import datetime, timedelta
        import pytz
        art = pytz.timezone("America/Argentina/Buenos_Aires")
        yesterday = (datetime.now(art) - timedelta(days=1)).strftime("%Y-%m-%d")

        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "meal",
            "meal": {
                "detected_food": "fideos con salsa",
                "meal_type": "dinner",
                "calories": 550,
                "proteins_g": 18,
                "carbs_g": 70,
                "fats_g": 15,
                "date_offset": -1,
            },
            "reply": "Registrado para ayer.",
        }))

        reply = await _send(client, "ayer a la noche comi fideos con salsa")
        assert len(reply) > 5

        import db
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM meals WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
            (TID,),
        ).fetchall()
        conn.close()

        assert len(rows) >= 1
        eaten_at = dict(rows[0])["eaten_at"]
        assert yesterday in eaten_at, f"Expected {yesterday} in {eaten_at}"


class TestStats:
    async def test_stats_shows_meals(self, client, _onboarded_user):
        import db
        user = db.get_user(TID)
        db.add_meal(
            user_id=user["id"],
            telegram_id=TID,
            description="ensalada",
            photo_path="",
            calories_est=300,
            meal_type="lunch",
            claude_analysis="",
        )

        reply = await _send(client, "/stats")
        assert "300" in reply or "kcal" in reply.lower()
        assert "ensalada" in reply.lower()

    async def test_stats_empty(self, client, _onboarded_user):
        reply = await _send(client, "/stats")
        assert "no registraste" in reply.lower() or "ninguna" in reply.lower()


class TestPlan:
    async def test_plan_returns_content(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "generate_meal_plan", _mock_generate_meal_plan())

        reply = await _send(client, "/plan")
        assert "plan" in reply.lower() or "kcal" in reply.lower() or "desayuno" in reply.lower()


class TestContextBetweenMessages:
    async def test_chat_history_persisted(self, client, _onboarded_user, monkeypatch):
        """After logging a meal, chat history should be saved so the next message has context."""
        import ai, db

        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "meal",
            "meal": {
                "detected_food": "empanadas de carne",
                "meal_type": "lunch",
                "calories": 500,
                "proteins_g": 25,
                "carbs_g": 40,
                "fats_g": 20,
            },
            "reply": "Empanadas registradas. 500 kcal.",
        }))

        await _send(client, "comi dos empanadas de carne")

        history = db.get_chat_history(TID)
        assert len(history) >= 2
        assert history[-2]["role"] == "user"
        assert "empanadas" in history[-2]["content"].lower()
        assert history[-1]["role"] == "assistant"


class TestCoachSwitch:
    async def test_coach_command(self, client, _onboarded_user):
        reply = await _send(client, "/coach")
        assert "1" in reply and "2" in reply

    async def test_coach_selection(self, client, _onboarded_user):
        await _send(client, "/coach")
        reply = await _send(client, "2")
        assert "roaster" in reply.lower() or "cambiado" in reply.lower() or "coach" in reply.lower()

        import db
        user = db.get_user(TID)
        assert user["coach_mode"] == "roaster"


class TestEdgeCases:
    async def test_empty_message(self, client, _onboarded_user):
        reply = await _send(client, "")
        assert len(reply) > 3
        assert "error" not in reply.lower()

    async def test_non_food_message(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "text",
            "content": "Jaja, que onda! Mandate una foto de tu comida y te ayudo.",
        }))

        reply = await _send(client, "jaja que pinta")
        assert len(reply) > 5


class TestReset:
    async def test_reset_clears_onboarding(self, client, _onboarded_user):
        reply = await _send(client, "/reset")
        assert "reset" in reply.lower() or "empezar" in reply.lower()

        import db
        user = db.get_user(TID)
        assert user["onboarding_complete"] == 0

    async def test_after_reset_gets_onboarding(self, client, _onboarded_user):
        await _send(client, "/reset")
        reply = await _send(client, "hola")
        assert "onboarding" in reply.lower() or "perfil" in reply.lower() or "coachkai" in reply.lower()


class TestIdentityUpdate:
    async def test_weight_update_persisted(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "identity_update",
            "update": {
                "identity_markdown": "Updated profile",
                "reason": "weight change",
                "weight_kg": 72,
            },
            "reply": "Perfil actualizado. Peso: 72 kg.",
        }))

        reply = await _send(client, "ahora peso 72 kg")
        assert "actualizado" in reply.lower() or "72" in reply

        import db
        user = db.get_user(TID)
        assert user["weight_kg"] == 72


class TestReminder:
    async def test_reminder_saved(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "set_reminder",
            "time_str": "14:00",
            "message": "Toma agua",
            "reply": "Recordatorio para las 14:00.",
        }))

        reply = await _send(client, "recordame a las 14 que tome agua")
        assert "14" in reply or "recordatorio" in reply.lower()

        import db
        reminders = db.get_pending_reminders()
        # May or may not be pending depending on current time, but at least check no crash
        # Instead check directly in DB
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM reminders WHERE telegram_id = ?", (TID,)
        ).fetchall()
        conn.close()
        assert len(rows) >= 1
        assert "agua" in dict(rows[0])["message"].lower()


class TestMemory:
    async def test_memory_saved(self, client, _onboarded_user, monkeypatch):
        import ai
        monkeypatch.setattr(ai, "process_message", _mock_process_message({
            "type": "save_memory",
            "content": "No le gusta el brocoli",
            "category": "preference",
            "reply": "Anotado.",
        }))

        reply = await _send(client, "no me gusta el brocoli")
        assert "anotado" in reply.lower() or len(reply) > 3

        import db
        memories = db.get_memories(TID)
        assert len(memories) >= 1
        assert "brocoli" in memories[0]["content"].lower()
