"""Simulate a full conversation with Coach Kai intake."""
import os, asyncio
os.environ['DATABASE_URL'] = ''
os.environ['GEMINI_API_KEY'] = open('.env').read().split('GEMINI_API_KEY=')[1].split()[0]
import db; db.init_db()
import ai

SEP = "-" * 50

async def test():
    tid = 88888
    db.upsert_user(tid, onboarding_complete=0)
    db.clear_intake_history(tid)
    
    convo = [
        "hola",
        "me llamo rafa",
        "tengo 26, peso 78kg, mido 178",
        "quiero bajar de peso, trabajo en una oficina",
        "voy al gym 3 veces por semana, hago pesas",
        "desayuno cafe con tostadas, almuerzo en la oficina (generalmente algo rapido), ceno en casa",
        "no tengo intolerancias, me gusta casi todo",
    ]
    
    history = []
    for i, msg in enumerate(convo):
        print(f"\n{SEP}")
        print(f"RAFA: {msg}")
        
        # Simulate what handlers.py does
        forced_done = False
        result = await ai.intake_turn(history, msg)
        
        if not result.get("done") and len(history) >= 12:
            print("[fallback triggered]")
            forced = await ai.force_extract_profile(history + [{"role": "user", "content": msg}])
            if forced:
                result = {"done": True, "profile": forced, "reply": forced.get("reply")}
                forced_done = True
        
        reply = result.get("reply", "")
        done = result.get("done", False)
        
        print(f"BOT: {reply}")
        
        if done:
            profile = result.get("profile", {})
            print(f"\n{'='*50}")
            print(f"ONBOARDING COMPLETE {'(via fallback)' if forced_done else '(via tool)'}")
            print(f"  name: {profile.get('name')}")
            print(f"  age: {profile.get('age')}")
            print(f"  weight: {profile.get('weight_kg')} kg")
            print(f"  height: {profile.get('height_cm')} cm")
            print(f"  goal: {profile.get('goal')}")
            print(f"  activity: {profile.get('activity_level')}")
            
            # Save to DB
            db.upsert_user(tid, onboarding_complete=1,
                name=profile.get("name"), age=profile.get("age"),
                weight_kg=profile.get("weight_kg"), height_cm=profile.get("height_cm"),
                goal=profile.get("goal"), activity_level=profile.get("activity_level"))
            
            # Verify saved
            user = db.get_user(tid)
            print(f"\n  DB verify: onboarding_complete={user.get('onboarding_complete')} name={user.get('name')}")
            break
        
        history = history + [
            {"role": "user", "content": msg},
            {"role": "assistant", "content": reply}
        ]

asyncio.run(test())
