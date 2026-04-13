import os, asyncio, sys
os.environ['DATABASE_URL'] = ''
os.environ['GEMINI_API_KEY'] = open('.env').read().split('GEMINI_API_KEY=')[1].split()[0]
import db; db.init_db()
import ai

TID = 99992

async def test():
    db.upsert_user(TID, onboarding_complete=1, name='Rafa', age=18,
        weight_kg=80, height_cm=180, goal='gain_muscle', activity_level='active')

    user = db.get_user(TID)
    
    tests = [
        "comi 3 facturas de manteca y un cafe con leche",
        "comi un cachafaz de chocolate",
        "comi pollo a la plancha con ensalada",
        "comi papas fritas con ketchup de la cafeteria",
        "comi una banana y unos manis",
    ]
    
    for msg in tests:
        result = await ai.process_message(msg, user, [])
        rtype = result.get("type","?")
        reply = result.get("reply") or result.get("content","")
        sys.stdout.buffer.write(f"\nU: {msg}\nB({rtype}): {str(reply)[:200]}\n".encode('utf-8'))

asyncio.run(test())
