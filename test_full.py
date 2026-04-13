"""Full bot simulation test - checks all features and DB state."""
import os, asyncio, json, sys
os.environ['DATABASE_URL'] = ''
os.environ['GEMINI_API_KEY'] = open('.env').read().split('GEMINI_API_KEY=')[1].split()[0]
import db; db.init_db()
import ai

SEP = "\n" + "="*60
TID = 99991

def cleanup_test_user():
    """Remove all test data for TID to ensure a clean slate."""
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM meals WHERE telegram_id=?", (TID,))
    c.execute("DELETE FROM workouts WHERE telegram_id=?", (TID,))
    c.execute("DELETE FROM reminders WHERE telegram_id=?", (TID,))
    c.execute("DELETE FROM memories WHERE telegram_id=?", (TID,))
    # Reset user profile to a clean state (chat_history, training_schedule, profile_text)
    c.execute("""UPDATE users SET chat_history=NULL, training_schedule=NULL, 
                 profile_text=NULL, onboarding_complete=0, name=NULL, age=NULL,
                 weight_kg=NULL, height_cm=NULL, goal=NULL, activity_level=NULL
                 WHERE telegram_id=?""", (TID,))
    conn.commit()
    conn.close()
    print(f"  Cleaned up all test data for TID={TID}")

def db_state():
    u = db.get_user(TID)
    meals = db.get_today_meals(TID)
    print(f"  DB > name={u.get('name')} age={u.get('age')} goal={u.get('goal')} training={u.get('training_schedule')} onboarding={u.get('onboarding_complete')}")
    print(f"  DB > meals_today={len(meals)} {[m.get('description','')[:30] for m in meals]}")

async def intake(convo):
    db.upsert_user(TID, onboarding_complete=0)
    db.clear_intake_history(TID)
    history = []
    for msg in convo:
        result = await ai.intake_turn(history, msg)
        if not result.get("done") and len(history) >= 12:
            forced = await ai.force_extract_profile(history + [{"role": "user", "content": msg}])
            if forced:
                result = {"done": True, "profile": forced, "reply": forced.get("reply")}
        reply = result.get("reply", "")
        done = result.get("done", False)
        sys.stdout.write(f"  U: {msg}\n  B: {reply[:120]}\n")
        if done:
            profile = result.get("profile", {})
            db.upsert_user(TID, onboarding_complete=1,
                name=profile.get("name"), age=profile.get("age"),
                weight_kg=profile.get("weight_kg"), height_cm=profile.get("height_cm"),
                goal=profile.get("goal"), activity_level=profile.get("activity_level"))
            if profile.get("identity_markdown"):
                db.save_profile_text(TID, profile["identity_markdown"])
            print(f"  --> ONBOARDING DONE")
            return True
        history = history + [
            {"role": "user", "content": msg},
            {"role": "assistant", "content": reply}
        ]
    return False

async def chat(msg, label=""):
    user = db.get_user(TID)
    history = db.get_chat_history(TID) if hasattr(db, 'get_chat_history') else []
    result = await ai.process_message(msg, user, history)
    rtype = result.get("type", "?")
    reply = result.get("reply") or result.get("content", "")
    
    # Handle meal saving
    if rtype == "meal":
        meal = result.get("meal", {})
        # Claude returns 'calories' (from log_meal tool), not 'calories_est'
        cal = int(meal.get("calories") or meal.get("calories_est", 0) or 0)
        db.add_meal(user["id"], TID, 
            meal.get("detected_food", msg)[:200], "",
            cal,
            meal.get("meal_type", "snack"), "",
            float(meal.get("proteins_g", 0) or 0),
            float(meal.get("carbs_g", 0) or 0),
            float(meal.get("fats_g", 0) or 0))
        reply_for_history = reply or f"Registr\u00e9: {meal.get('detected_food', msg)} (~{cal} kcal)."
    elif rtype == "identity_update":
        upd = result.get("update", {})
        kwargs = {}
        if upd.get("training_schedule"): kwargs["training_schedule"] = upd["training_schedule"]
        if upd.get("weight_kg"): kwargs["weight_kg"] = upd["weight_kg"]
        if kwargs: db.upsert_user(TID, **kwargs)
        if upd.get("identity_markdown"): db.save_profile_text(TID, upd["identity_markdown"])
        reply_for_history = reply or "\u2705 Perfil actualizado."
    else:
        reply_for_history = reply or ""
    
    # Save chat history for context carry-over
    new_history = (history + [
        {"role": "user", "content": msg},
        {"role": "assistant", "content": reply_for_history},
    ])[-20:]
    db.save_chat_history(TID, new_history)
    
    tag = f"[{label}] " if label else ""
    sys.stdout.write(f"  U: {msg}\n  B({rtype}): {str(reply)[:150]}\n")

async def main():
    # Clean up any previous test run data
    cleanup_test_user()
    
    # PHASE 1: ONBOARDING
    print(SEP)
    print("PHASE 1: ONBOARDING")
    ok = await intake([
        "hola",
        "me llamo rafa, tengo 18",
        "peso 80kg, mido 180",
        "quiero ganar musculo",
        "voy al gym martes, jueves y sabados a las 9am",
        "como 3 veces al dia, desayuno, almuerzo y cena",
        "no tengo intolerancias, me gusta la carne y la pasta",
    ])
    print(f"  Onboarding OK: {ok}")
    db_state()

    # PHASE 2: TRAINING SCHEDULE
    print(SEP)
    print("PHASE 2: TRAINING SCHEDULE")
    await chat("entreno los martes, jueves y sabados a las 9am", "training")
    db_state()

    # PHASE 3: MEAL LOGGING - PAST TENSE (should log)
    print(SEP)
    print("PHASE 3: MEAL LOGGING (past tense = should log)")
    await chat("comi una milanesa con pure", "past-meal")
    db_state()

    # PHASE 4: FUTURE TENSE (should NOT log)
    print(SEP)
    print("PHASE 4: FUTURE TENSE (should NOT log)")
    meals_before = len(db.get_today_meals(TID))
    await chat("me voy a pedir unos franuis", "future-no-log")
    meals_after = len(db.get_today_meals(TID))
    print(f"  Meals before={meals_before} after={meals_after} - {'OK: did NOT log' if meals_after == meals_before else 'FAIL: logged future food!'}")

    # PHASE 5: ARGENTINE FOOD
    print(SEP)
    print("PHASE 5: ARGENTINE FOOD KNOWLEDGE")
    await chat("comi 6 rumbas de desayuno", "rumbas")
    await chat("tome un mate con dos medialunas de manteca", "medialunas")
    db_state()

    # PHASE 6: MEMORY RECALL
    print(SEP)
    print("PHASE 6: MEMORY RECALL")
    await chat("a que hora entreno los sabados?", "recall-training")
    await chat("cuanto pesa rafa?", "recall-weight")
    await chat("cuantas calorias llevo hoy?", "recall-calories")

asyncio.run(main())
