"""
test_telegram.py — End-to-end test of NutriBot via Telegram Bot API.

Simulates a user conversation by calling handlers with mock Update objects,
then sends the results to Rafa's chat so he can see how responses look.

Usage: python test_telegram.py
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RAFA_ID = 1557872061  # Rafa's Telegram ID

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not set in .env")
    sys.exit(1)
if not ANTHROPIC_KEY:
    print("❌ ANTHROPIC_API_KEY not set in .env")
    sys.exit(1)

# Set env for ai.py
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_KEY


async def run_tests():
    from telegram import Bot
    import db
    import ai
    import handlers
    import charts as charts_module

    bot = Bot(token=TELEGRAM_TOKEN)

    async def send(text: str, **kwargs):
        """Send a message to Rafa's chat as the bot."""
        await bot.send_message(chat_id=RAFA_ID, text=text, **kwargs)
        await asyncio.sleep(0.5)

    async def send_section(title: str):
        await bot.send_message(chat_id=RAFA_ID, text=f"{'─'*30}\n🧪 *{title}*", parse_mode="Markdown")
        await asyncio.sleep(0.5)

    # --- Init DB ---
    db.init_db()

    # --- Make sure test user exists ---
    db.upsert_user(
        RAFA_ID,
        name="Rafa",
        age=23,
        weight_kg=75,
        height_cm=178,
        goal="gain_muscle",
        activity_level="moderate",
        onboarding_complete=1,
    )
    user = db.get_user(RAFA_ID)

    print("🚀 Starting NutriBot e2e tests...")
    await send("🤖 *NutriBot — Test Suite*\nTestando todas las funcionalidades...")
    await asyncio.sleep(1)

    # ── 1. /ayuda ────────────────────────────────────────────────────────────
    await send_section("1. /ayuda")
    mock_update = make_update(RAFA_ID, "/ayuda")
    mock_ctx = make_context()
    await handlers.cmd_ayuda(mock_update, mock_ctx)
    await send(f"✅ /ayuda → {get_reply(mock_update)[:80]}...")

    # ── 2. /perfil ───────────────────────────────────────────────────────────
    await send_section("2. /perfil")
    mock_update = make_update(RAFA_ID, "/perfil")
    mock_ctx = make_context()
    await handlers.cmd_perfil(mock_update, mock_ctx)
    await send(f"✅ /perfil → {get_reply(mock_update)[:120]}...")

    # ── 3. Nutrition question (not food log) ─────────────────────────────────
    await send_section("3. Pregunta nutrición")
    q = "cuánta proteína necesito por día?"
    result = await ai.answer_nutrition_question(q, user)
    await bot.send_message(chat_id=RAFA_ID, text=f"🧪 Usuario pregunta: '{q}'\n\nBot responde:\n{result}")

    # ── 4. Food log — text ───────────────────────────────────────────────────
    await send_section("4. Registro comida texto")
    analysis = await ai.analyze_meal_text("200g de pollo a la plancha con ensalada", user)
    resp = analysis.get("full_response", "sin respuesta")
    cost = ai.get_turn_cost()
    await bot.send_message(
        chat_id=RAFA_ID,
        text=f"🧪 Usuario: 'comí 200g pollo a la plancha'\n\nBot responde:\n{resp}\n\n💰 ${cost:.5f} USD"
    )
    ai.reset_turn_cost()

    # ── 5. Vague meal check ──────────────────────────────────────────────────
    await send_section("5. Comida vaga")
    for vague in ["comí pasta", "almorcé", "desayuné algo"]:
        followup = await ai.check_meal_vague(vague)
        status = "pregunta follow-up ✅" if followup else "pasa directo ❌"
        fq = f": '{followup[:60]}'" if followup else ""
        await send(f"'{vague}' → {status}{fq}")

    # ── 6. Intent classification ─────────────────────────────────────────────
    await send_section("6. Clasificación de intención")
    tests = [
        ("comí milanesa", "log"),
        ("cuántas calorías tiene un huevo?", "question"),
        ("como se calcula el camino más corto?", "other"),
        ("qué hora es", "other"),
        ("me duele la panza después de comer", "question"),
    ]
    for msg, expected in tests:
        result = await ai.classify_message(msg)
        icon = "✅" if result == expected else "❌"
        await send(f"{icon} '{msg}'\n→ got: {result} | expected: {expected}")

    # ── 7. /stats preview ────────────────────────────────────────────────────
    await send_section("7. /stats preview")
    # Add a test meal first
    db.add_meal(user["id"], RAFA_ID, "pollo 200g test", "", 300, "lunch", "", 35, 0, 10)
    mock_update = make_update(RAFA_ID, "/stats")
    mock_ctx = make_context()
    await handlers.cmd_stats(mock_update, mock_ctx)
    reply = get_reply(mock_update)
    await bot.send_message(chat_id=RAFA_ID, text=f"🧪 /stats output:\n\n{reply}", parse_mode="Markdown")
    # Clean up test meal
    db.delete_last_meal(RAFA_ID)

    # ── 8. /resumen chart ────────────────────────────────────────────────────
    await send_section("8. /resumen chart")
    db.add_meal(user["id"], RAFA_ID, "pollo 200g", "", 320, "lunch", "", 38, 5, 12)
    db.add_meal(user["id"], RAFA_ID, "tostadas con manteca", "", 180, "breakfast", "", 5, 22, 8)
    meals = db.get_today_meals(RAFA_ID)
    daily_goal = charts_module.estimate_daily_calories(user)
    total_cal = sum(m.get("calories_est", 0) or 0 for m in meals)
    try:
        png_bytes = await charts_module.generate_daily_summary_chart(user, meals)
        caption = await ai.generate_chart_caption(user, meals, total_cal, daily_goal)
        await bot.send_photo(chat_id=RAFA_ID, photo=png_bytes, caption=f"🧪 /resumen output:\n{caption}")
        await send("✅ Chart generado OK")
    except Exception as e:
        await send(f"❌ Chart error: {e}")
    # clean up
    db.delete_last_meal(RAFA_ID)
    db.delete_last_meal(RAFA_ID)

    # ── Done ─────────────────────────────────────────────────────────────────
    await send("✅ *Tests completados!* Revisá arriba cómo quedaron las respuestas.", parse_mode="Markdown")
    print("✅ Done")


def make_update(telegram_id: int, text: str):
    """Create a minimal mock Update object."""
    update = MagicMock()
    update.effective_user.id = telegram_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


def make_context():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = MagicMock()
    return ctx


def get_reply(mock_update) -> str:
    """Get the last reply_text call argument."""
    calls = mock_update.message.reply_text.call_args_list
    if calls:
        return str(calls[-1].args[0]) if calls[-1].args else ""
    return "(sin respuesta)"


if __name__ == "__main__":
    asyncio.run(run_tests())
