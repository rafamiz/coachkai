content = open('ai.py', encoding='utf-8').read()

old = '- Solo pod\u00e9s hacer UNA pregunta si el alimento es completamente ambiguo'
add = (
    '- Cuando registr\u00e9s una comida, SIEMPRE inclu\u00ed un comentario breve (1 l\u00ednea) junto al tool call.\n'
    '- Si la comida es poco saludable (facturas, fritos, dulces, ultraprocesados), dec\u00edselo directamente: '
    '"3 facturas son ~360 kcal de pura grasa, compen\u00e1 hoy." o "Eso no suma a tu objetivo."\n'
    '- Si es saludable, un comentario positivo breve.\n'
    + old
)

if old in content:
    content = content.replace(old, add, 1)
    open('ai.py', 'w', encoding='utf-8').write(content)
    print('OK')
else:
    print('NOT FOUND')
