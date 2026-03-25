content = open('ai.py', encoding='utf-8').read()

# Find the REGISTRO INMEDIATO section and add reply requirement
old = '"Solo pod\\u00e9s hacer UNA pregunta si el alimento es completamente ambiguo'
new = (
    '"Cuando registr\\u00e9s una comida, SIEMPRE inclu\\u00ed un comentario breve (1 l\\u00ednea) junto al tool call. "'
    '\n    "Si la comida es saludable: comentario positivo breve. "'
    '\n    "Si la comida es poco saludable (facturas, fritos, dulces, ultraprocesados): dec\\u00edselo sin rodeos. "'
    '\n    "Ejemplos: \\'3 facturas de manteca son ~360 kcal de pura grasa. Equ\\u00e4libr\\u00e1 hoy.\\' / \\'Papas fritas no suman nada bueno a tu objetivo, Rafa.\\' / \\'Pollo con ensalada, perfecto para ganar m\\u00fasculo.\\' "'
    '\n    "Solo pod\\u00e9s hacer UNA pregunta si el alimento es completamente ambiguo'
)

if old in content:
    content = content.replace(old, new, 1)
    with open('ai.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched OK")
else:
    print("NOT FOUND")
    idx = content.find('Solo pod')
    print(repr(content[idx:idx+100]))
