content = open('ai.py', encoding='utf-8').read()

old = '"Tus respuestas son CORTAS: m\\u00e1ximo 2-3 l\\u00edneas. Sin introducciones ni sermones. "'
new = (
    '"Tus respuestas son CORTAS: m\\u00e1ximo 2-3 l\\u00edneas. Sin introducciones ni sermones. "'
    '\n    "HONESTIDAD NUTRICIONAL: cuando el usuario come algo poco saludable (ultraprocesados, mucho az\\u00facar, exceso de calor\\u00edas vac\\u00edas), dec\\u00edselo directamente pero sin sermonear. "'
    '\n    "Ac\\u00faat\\u00e9 como un coach real: \'Eso estuvo pesado, compensalo en la cena.\' o \'Dale, pero equ\\u00e4libr\\u00e1 con algo liviano hoy.\' "'
    '\n    "No elogies comidas malas. No hagas like a cada cosa. Honesto, directo y breve. "'
)

if old in content:
    content = content.replace(old, new, 1)
    with open('ai.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched OK")
else:
    print("NOT FOUND - searching context:")
    idx = content.find('CORTAS')
    print(repr(content[idx-10:idx+100]))
