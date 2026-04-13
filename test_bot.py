import os, asyncio, sys
os.environ['ANTHROPIC_API_KEY'] = open('.env').read().split('ANTHROPIC_API_KEY=')[1].split()[0]
os.environ['DATABASE_URL'] = ''
sys.path.insert(0, '.')
import db; db.init_db()
import ai

USER = {
    'name': 'Rafa', 'age': 23, 'weight_kg': 75, 'height_cm': 178,
    'goal': 'gain_muscle', 'activity_level': 'active',
    'telegram_id': 99999, 'id': 1,
    'profile_text': 'Rafa, 23 años, 75kg, objetivo ganar músculo, activo.'
}

TESTS = [
    ('saludo',                   'hola, buenos días'),
    ('registrar comida',         'comi 2 huevos revueltos con tostadas'),
    ('pregunta nutrición',       'cuanta proteina necesito por dia?'),
    ('cambio de tema',           'che, que onda'),
    ('recordatorio',             'avisame a las 21:00'),
    ('recordatorio lenguaje nat','recordame a las 9am'),
    ('entrenamiento',            'hice 45 min de gym, día de piernas'),
    ('save memory',              'recorda que soy intolerante a la lactosa'),
    ('sin bloqueo previo',       'cuantas calorias tiene una manzana?'),
    ('foto comida (texto)',       'comi una milanesa con papas fritas y ensalada'),
    ('borrar comida',            'borrá el desayuno que registré'),
    ('topic change mid-conv',    'cuanto es 2+2'),
]

async def run_tests():
    history = []
    results = []
    for name, msg in TESTS:
        history_copy = list(history)
        history.append({'role': 'user', 'content': msg})
        try:
            result = await ai.process_message(msg, USER, history_copy)
            t = result.get('type', '?')
            
            if t == 'meal':
                m = result.get('meal', result)
                desc = m.get('detected_food') or m.get('description', '?')
                cal = m.get('calories_est') or m.get('calories', 0)
                content = '[MEAL] ' + desc + ' ~' + str(cal) + ' kcal'
            elif t == 'workout':
                w = result.get('workout', {})
                content = '[WORKOUT] ' + w.get('description', '?') + ' ' + str(w.get('calories_burned', 0)) + ' kcal'
            elif t == 'set_reminder':
                content = '[REMINDER at ' + str(result.get('time_str', '?')) + '] ' + str(result.get('message', ''))
            elif t == 'save_memory':
                content = '[MEMORY:' + result.get('category', '?') + '] ' + result.get('content', '')[:60]
            elif t == 'delete_meal':
                content = '[DELETE_MEAL] meal_id=' + str(result.get('meal_id', '?'))
            else:
                content = result.get('content') or result.get('reply') or ''
            
            # Check encoding
            bad = '???????' in content
            ok = 'OK' if not bad else 'ENCODING ERROR'
            print(ok + ' [' + t + '] ' + name + ': ' + content[:90])
            history.append({'role': 'assistant', 'content': content[:100]})
            results.append((name, ok, t))
        except Exception as e:
            print('ERROR ' + name + ': ' + str(e))
            results.append((name, 'ERROR', str(e)))
    
    print('\n--- SUMMARY ---')
    ok_count = sum(1 for _, s, _ in results if s == 'OK')
    print(str(ok_count) + '/' + str(len(results)) + ' tests passed')

asyncio.run(run_tests())
