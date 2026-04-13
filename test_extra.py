"""Extra bot feature tests."""
import os, asyncio, sys, sqlite3
# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ['DATABASE_URL'] = ''
os.environ['GEMINI_API_KEY'] = open('.env').read().split('GEMINI_API_KEY=')[1].split()[0]
import db; db.init_db()
import ai

TID = 99992  # Different TID to avoid collision with test_full

PASS = "\u2705 PASS"
FAIL = "\u274c FAIL"

results = {}

def setup_user():
    """Create a basic test user with onboarding complete."""
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM meals WHERE telegram_id=?", (TID,))
    c.execute("DELETE FROM workouts WHERE telegram_id=?", (TID,))
    c.execute("DELETE FROM reminders WHERE telegram_id=?", (TID,))
    c.execute("DELETE FROM memories WHERE telegram_id=?", (TID,))
    c.execute("""UPDATE users SET chat_history=NULL, training_schedule=NULL,
                 profile_text=NULL, onboarding_complete=0, name=NULL, age=NULL,
                 weight_kg=NULL, height_cm=NULL, goal=NULL, activity_level=NULL
                 WHERE telegram_id=?""", (TID,))
    conn.commit()
    conn.close()
    db.upsert_user(TID, onboarding_complete=1, name="TestUser", age=25,
                   weight_kg=75.0, height_cm=175.0, goal="maintain",
                   activity_level="active")
    print(f"  User setup complete for TID={TID}")

async def chat(msg, history=None):
    user = db.get_user(TID)
    if history is None:
        history = db.get_chat_history(TID) or []
    result = await ai.process_message(msg, user, history)
    rtype = result.get("type", "?")
    reply = result.get("reply") or result.get("content", "")
    
    if rtype == "meal":
        meal = result.get("meal", {})
        cal = int(meal.get("calories") or meal.get("calories_est", 0) or 0)
        db.add_meal(user["id"], TID,
            meal.get("detected_food", msg)[:200], "", cal,
            meal.get("meal_type", "snack"), "",
            float(meal.get("proteins_g", 0) or 0),
            float(meal.get("carbs_g", 0) or 0),
            float(meal.get("fats_g", 0) or 0))
        reply_for_history = reply or f"Registr\u00e9: {meal.get('detected_food',msg)} (~{cal} kcal)."
    elif rtype == "identity_update":
        upd = result.get("update", {})
        kwargs = {}
        if upd.get("weight_kg"): kwargs["weight_kg"] = upd["weight_kg"]
        if upd.get("training_schedule"): kwargs["training_schedule"] = upd["training_schedule"]
        if kwargs: db.upsert_user(TID, **kwargs)
        if upd.get("identity_markdown"): db.save_profile_text(TID, upd["identity_markdown"])
        reply_for_history = reply or "\u2705 Perfil actualizado."
    elif rtype == "set_reminder":
        db.save_reminder(TID, result.get("time_str", ""), result.get("message", ""))
        reply_for_history = reply or "\u23f0 Reminder set."
    else:
        reply_for_history = reply or ""
    
    new_history = ((history or []) + [
        {"role": "user", "content": msg},
        {"role": "assistant", "content": reply_for_history},
    ])[-20:]
    db.save_chat_history(TID, new_history)
    
    return result, rtype, reply

async def test1_reminder():
    """Test 1: 'avisame a las 6pm que tome proteina' -> expect type=set_reminder"""
    print("\n--- Test 1: Reminder ---")
    result, rtype, reply = await chat("avisame a las 6pm que tome proteina")
    print(f"  type={rtype}, time={result.get('time_str','?')}, msg={result.get('message','?')[:60]}")
    ok = rtype == "set_reminder" and result.get("time_str", "") in ("18:00", "18:00:00")
    print(f"  {PASS if ok else FAIL}: Expected type=set_reminder with time=18:00, got type={rtype} time={result.get('time_str','?')}")
    results["reminder"] = ok

async def test2_weight_update():
    """Test 2: 'hoy me pese y peso 79kg' -> expect weight updated in DB"""
    print("\n--- Test 2: Weight Update ---")
    result, rtype, reply = await chat("hoy me pese y peso 79kg")
    print(f"  type={rtype}, reply={reply[:80]}")
    user = db.get_user(TID)
    weight = user.get("weight_kg")
    ok = rtype == "identity_update" and abs((weight or 0) - 79.0) < 0.5
    print(f"  {PASS if ok else FAIL}: Expected weight=79kg in DB, got weight={weight}, type={rtype}")
    results["weight_update"] = ok

async def test3_empanada_calories():
    """Test 3: 'comi una empanada de carne' -> expect ~200kcal"""
    print("\n--- Test 3: Empanada Calories ---")
    result, rtype, reply = await chat("comi una empanada de carne")
    print(f"  type={rtype}, reply={reply[:80]}")
    meal = result.get("meal", {})
    cal = int(meal.get("calories") or meal.get("calories_est", 0) or 0)
    ok = rtype == "meal" and 150 <= cal <= 300
    print(f"  {PASS if ok else FAIL}: Expected ~200kcal, got {cal} kcal (type={rtype})")
    results["empanada_calories"] = ok

async def test4_arroz_pollo():
    """Test 4: 'comi medio plato de arroz con pollo' -> expect reasonable calories"""
    print("\n--- Test 4: Arroz con Pollo ---")
    result, rtype, reply = await chat("comi medio plato de arroz con pollo")
    print(f"  type={rtype}, reply={reply[:80]}")
    meal = result.get("meal", {})
    cal = int(meal.get("calories") or meal.get("calories_est", 0) or 0)
    ok = rtype == "meal" and 200 <= cal <= 600
    print(f"  {PASS if ok else FAIL}: Expected 200-600kcal (half plate arroz+pollo), got {cal} kcal (type={rtype})")
    results["arroz_pollo"] = ok

async def test5_offtopic():
    """Test 5: 'cuanto vale el dolar?' -> should redirect politely (type=text)"""
    print("\n--- Test 5: Off-topic (dolar) ---")
    result, rtype, reply = await chat("cuanto vale el dolar?")
    print(f"  type={rtype}, reply={reply[:120]}")
    ok = rtype == "text" and len(reply) > 10  # Should give a text redirect, not log
    print(f"  {PASS if ok else FAIL}: Expected type=text (redirect), got type={rtype}")
    results["offtopic_redirect"] = ok

async def test6_context_carryover():
    """Test 6: 3 related messages, check context carry-over"""
    print("\n--- Test 6: Context Carry-over ---")
    # Clear chat history for fresh start
    db.save_chat_history(TID, [])
    
    _, _, r1 = await chat("me llamo Tomas y tengo 30 años")
    print(f"  Turn 1: {r1[:80]}")
    
    _, _, r2 = await chat("peso 85kg y mido 178cm")
    print(f"  Turn 2: {r2[:80]}")
    
    _, _, r3 = await chat("que nombre te dije antes?")
    print(f"  Turn 3: {r3[:80]}")
    
    # Context carry-over: bot should remember "Tomas" from 2 turns ago
    ok = "tomas" in r3.lower() or "tom\u00e1s" in r3.lower()
    print(f"  {PASS if ok else FAIL}: Expected bot to remember name 'Tomas', reply: {r3[:80]}")
    results["context_carryover"] = ok

async def main():
    print("="*60)
    print("EXTRA TESTS - Coach Kai")
    print("="*60)
    
    setup_user()
    
    await test1_reminder()
    await test2_weight_update()
    await test3_empanada_calories()
    await test4_arroz_pollo()
    await test5_offtopic()
    await test6_context_carryover()
    
    print("\n" + "="*60)
    print("RESULTS SUMMARY:")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for k, v in results.items():
        print(f"  {PASS if v else FAIL}: {k}")
    print(f"\n  {passed}/{total} tests passed")
    print("="*60)

asyncio.run(main())
