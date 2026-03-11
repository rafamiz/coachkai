"""
QA tests for NutriBot — tests what can be verified without Telegram.
Run: python test_bot.py
"""
import asyncio
import os
import sys

# Minimal env for testing
os.environ.setdefault("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
os.environ.setdefault("DATABASE_URL", "")  # use SQLite locally

PASS = "✅"
FAIL = "❌"
results = []

def report(name, passed, detail=""):
    icon = PASS if passed else FAIL
    msg = f"{icon} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append((name, passed))


# ── 1. NUTRITION.PY ──────────────────────────────────────────────────────────

async def test_nutrition():
    print("\n── nutrition.py ──")
    import nutrition as nutr

    # parse_grams
    report("parse_grams '200g'", nutr.parse_grams("200g") == 200.0)
    report("parse_grams 'sin gramos'", nutr.parse_grams("un plato grande") is None)

    # estimate_grams
    report("estimate_grams 'plato'", nutr.estimate_grams("un plato grande") > 0)
    report("estimate_grams fallback", nutr.estimate_grams("xyz desconocido") == 150)

    # lookup_food — may fail if OFF is down
    food = await nutr.lookup_food("pollo")
    if food:
        report("OFF lookup 'pollo'", food["kcal_per_100g"] > 0, f"{food['kcal_per_100g']} kcal/100g")
    else:
        report("OFF lookup 'pollo'", False, "API no disponible o timeout")

    # get_nutrition_for_meal
    result = await nutr.get_nutrition_for_meal("arroz", "200g")
    if result:
        report("get_nutrition arroz 200g", result["calories"] > 0, f"{result['calories']} kcal, {result['proteins_g']}g prot")
    else:
        report("get_nutrition arroz 200g", False, "no encontrado")


# ── 2. DB.PY ─────────────────────────────────────────────────────────────────

def test_db():
    print("\n── db.py ──")
    import db
    db.init_db()

    # upsert + get user
    db.upsert_user(9999999, name="Test User", age=25, weight_kg=70, height_cm=175,
                   goal="maintain", activity_level="moderate", onboarding_complete=1)
    user = db.get_user(9999999)
    report("upsert + get_user", user is not None and user["name"] == "Test User")

    # add + get meal
    user_id = user["id"]
    db.add_meal(user_id, 9999999, "pollo 200g", "", 300, "lunch", '{"note": "test"}', 30, 10, 5)
    meals = db.get_today_meals(9999999)
    report("add + get_today_meals", len(meals) > 0)

    # delete last meal
    deleted = db.delete_last_meal(9999999)
    report("delete_last_meal", deleted is not None, f"deleted: '{deleted}'")

    # onboarding token
    token = db.create_onboarding_token(9999999)
    report("create_onboarding_token", len(token) > 10)
    tid = db.get_telegram_id_by_token(token)
    report("get_telegram_id_for_token", tid == 9999999)

    # eating schedule
    db.upsert_eating_schedule(user_id, "lunch", 12, 30, 0, 0)
    schedules = db.get_all_eating_schedules()
    report("upsert + get_all_eating_schedules", any(s["user_id"] == user_id for s in schedules))

    # cleanup test user
    conn = db.get_conn()
    c = db._cur(conn)
    c.execute(db._q("DELETE FROM meals WHERE telegram_id = ?"), (9999999,))
    c.execute(db._q("DELETE FROM eating_schedule WHERE user_id = ?"), (user_id,))
    c.execute(db._q("DELETE FROM users WHERE telegram_id = ?"), (9999999,))
    conn.commit()
    db._release(conn)
    report("cleanup test user", True)


# ── 3. AI.PY — intent classification ─────────────────────────────────────────

async def test_ai_intent():
    print("\n── ai.py intent classification ──")
    import ai

    food_messages = ["comí pasta", "almorcé pollo con arroz", "desayuné medialunas", "tomé mate"]
    non_food = ["hola como estas", "como se calcula el camino más corto", "qué hora es"]

    for msg in food_messages:
        result = await ai.classify_intent(msg)
        report(f"classify food: '{msg}'", result is True)

    for msg in non_food:
        result = await ai.classify_intent(msg)
        report(f"classify non-food: '{msg}'", result is False)


# ── 4. AI.PY — vagueness check ───────────────────────────────────────────────

async def test_ai_vague():
    print("\n── ai.py vagueness check ──")
    import ai

    vague = ["comí", "almorcé", "comí pasta"]  # should ask follow-up
    specific = ["comí un plato grande de pasta con tuco", "200g de pollo a la plancha"]

    for msg in vague:
        result = await ai.check_meal_vague(msg)
        report(f"vague: '{msg}'", result is not None, result[:50] if result else "None")

    for msg in specific:
        result = await ai.check_meal_vague(msg)
        report(f"specific: '{msg}'", result is None, "OK" if result is None else result[:50])


# ── 5. AI.PY — meal analysis ─────────────────────────────────────────────────

async def test_ai_analysis():
    print("\n── ai.py meal analysis ──")
    import ai

    mock_user = {
        "name": "Test",
        "age": 25,
        "weight_kg": 70,
        "height_cm": 175,
        "goal": "maintain",
        "activity_level": "moderate",
    }

    result = await ai.analyze_meal_text("200g de pollo a la plancha", mock_user)
    report("analyze_meal returns calories", result.get("calories", 0) > 0, f"{result.get('calories')} kcal")
    report("analyze_meal returns proteins", result.get("proteins_g", 0) > 0, f"{result.get('proteins_g')}g")
    report("analyze_meal returns meal_type", result.get("meal_type") in ["breakfast","lunch","dinner","snack"])
    report("analyze_meal returns full_response", bool(result.get("full_response")))

    # Edge case: weird input
    result2 = await ai.analyze_meal_text("xyz 123 !@#", mock_user)
    report("analyze_meal edge case no crash", result2 is not None)


# ── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 50)
    print("NutriBot QA Tests")
    print("=" * 50)

    test_db()
    await test_nutrition()
    await test_ai_intent()
    await test_ai_vague()
    await test_ai_analysis()

    print("\n" + "=" * 50)
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("Failed:")
        for name, p in results:
            if not p:
                print(f"  ❌ {name}")
    print("=" * 50)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
