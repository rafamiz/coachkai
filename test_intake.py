import os, asyncio, sys
os.environ['DATABASE_URL'] = ''
os.environ['GEMINI_API_KEY'] = open('.env').read().split('GEMINI_API_KEY=')[1].split()[0]
import db; db.init_db()
import ai

async def test():
    tid = 77777
    db.upsert_user(tid, onboarding_complete=0)
    db.clear_intake_history(tid)
    
    convo = [
        'hola quiero empezar',
        'rafa',
        '26 anos',
        '78kg, 178cm',
        'quiero bajar de peso',
        'voy al gym 3 veces por semana',
        'como bien, desayuno cafe con tostadas, almuerzo en oficina, ceno en casa',
    ]
    
    history = []
    for i, msg in enumerate(convo):
        result = await ai.intake_turn(history, msg)
        reply = result.get('reply', '')
        done = result.get('done', False)
        print(f'[{i+1}] done={done} reply_len={len(reply)} history_len={len(history)}')
        if done:
            profile = result.get('profile', {})
            print(f'  -> name={profile.get("name")} goal={profile.get("goal")} weight={profile.get("weight_kg")}')
            break
        history = history + [
            {'role': 'user', 'content': msg},
            {'role': 'assistant', 'content': reply}
        ]
    else:
        print('NOT DONE after all messages - fallback test:')
        forced = await ai.force_extract_profile(history)
        print(f'  forced: {forced}')

asyncio.run(test())
