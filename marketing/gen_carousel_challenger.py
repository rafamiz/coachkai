"""
Generate a 7-slide Instagram/TikTok carousel for CoachKai - Coach Identity focus.
Highlights the Challenger personality with WhatsApp chat mockups.
Format: 1080x1350 (4:5 portrait).
"""

from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1350

# ── Colors ──────────────────────────────────────────────────────────────
BG_DARK = (10, 10, 15)
BG_CARD = (19, 19, 31)
PRIMARY = (99, 102, 241)
ACCENT = (168, 85, 247)
GREEN = (34, 197, 94)
WA_GREEN = (37, 211, 102)
WA_BG = (11, 20, 27)
WA_BUBBLE_IN = (30, 45, 54)     # incoming message bubble (coach)
WA_BUBBLE_OUT = (0, 92, 75)     # outgoing message bubble (user)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)
ORANGE = (251, 146, 60)
RED_SOFT = (239, 68, 68)
YELLOW = (250, 204, 21)
CYAN = (34, 211, 238)


def get_font(size, bold=False):
    names = (
        ["arialbd.ttf", "Arial Bold.ttf", "segoeui.ttf"] if bold
        else ["arial.ttf", "Arial.ttf", "segoeui.ttf"]
    )
    for name in names:
        for base in ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/System/Library/Fonts"]:
            path = os.path.join(base, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()


def gradient_bg(draw, w, h, top_color, bot_color):
    for y in range(h):
        ratio = y / h
        r = int(top_color[0] * (1 - ratio) + bot_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bot_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bot_color[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def rounded_rect(draw, xy, fill, radius=30):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_centered_text(draw, y, text, font, fill=WHITE, max_width=900):
    lines = []
    words = text.split()
    current_line = ""
    for word in words:
        test = (current_line + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test
    if current_line:
        lines.append(current_line)

    line_height = draw.textbbox((0, 0), "Ay", font=font)[3] + 8
    cur_y = y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        draw.text(((W - lw) // 2, cur_y), line, font=font, fill=fill)
        cur_y += line_height
    return cur_y


def draw_wa_chat_bubble(draw, x, y, text, font, is_incoming=True, max_w=720, time_str="20:20"):
    """Draw a WhatsApp-style chat bubble. Returns bottom y."""
    bg = WA_BUBBLE_IN if is_incoming else WA_BUBBLE_OUT
    padding_x, padding_y = 24, 16

    # Word wrap
    lines = []
    words = text.split()
    current_line = ""
    for word in words:
        test = (current_line + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_w - 2 * padding_x - 80 and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test
    if current_line:
        lines.append(current_line)

    line_h = draw.textbbox((0, 0), "Ay", font=font)[3] + 6
    text_h = line_h * len(lines)

    # Calculate bubble width from longest line
    max_line_w = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        if lw > max_line_w:
            max_line_w = lw

    bubble_w = max_line_w + 2 * padding_x + 80  # extra for time
    bubble_h = text_h + 2 * padding_y + 4

    # Position: incoming = left, outgoing = right
    if is_incoming:
        bx = x
    else:
        bx = W - x - bubble_w

    rounded_rect(draw, (bx, y, bx + bubble_w, y + bubble_h), fill=bg, radius=16)

    # Draw text lines
    ty = y + padding_y
    for line in lines:
        draw.text((bx + padding_x, ty), line, font=font, fill=WHITE)
        ty += line_h

    # Time stamp
    f_time = get_font(20)
    draw.text((bx + bubble_w - 80, y + bubble_h - 28), time_str, font=f_time, fill=(160, 175, 190))

    return y + bubble_h + 12


def draw_wa_header(draw, y, name="Coach Kai", subtitle="en linea"):
    """Draw a WhatsApp-style chat header."""
    # Header bar
    draw.rectangle([(0, y), (W, y + 80)], fill=(32, 44, 52))

    f_name = get_font(28, bold=True)
    f_sub = get_font(22)

    # Back arrow
    draw.text((20, y + 25), "<", font=f_name, fill=MUTED)

    # Avatar circle
    cx, cy = 90, y + 40
    draw.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=PRIMARY)
    f_avatar = get_font(22, bold=True)
    draw.text((cx - 8, cy - 12), "K", font=f_avatar, fill=WHITE)

    # Name & status
    draw.text((125, y + 15), name, font=f_name, fill=WHITE)
    draw.text((125, y + 47), subtitle, font=f_sub, fill=WA_GREEN)

    return y + 80


# ── Slides ──────────────────────────────────────────────────────────────

def slide_1_hook():
    """HOOK: Your coach, your rules."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (25, 5, 45), (5, 5, 15))

    f_small = get_font(30)
    f_big = get_font(64, bold=True)
    f_mid = get_font(42, bold=True)
    f_body = get_font(34)

    # Top badge
    badge = "DESLIZA PARA VER"
    bbox = draw.textbbox((0, 0), badge, font=f_small)
    bw = bbox[2] - bbox[0] + 50
    rounded_rect(draw, ((W - bw) // 2, 80, (W + bw) // 2, 135), fill=RED_SOFT, radius=25)
    draw.text(((W - bbox[2] + bbox[0]) // 2, 87), badge, font=f_small, fill=WHITE)

    # Main text
    y = 250
    y = draw_centered_text(draw, y, "Imaginate un", f_big, MUTED)
    y = draw_centered_text(draw, y + 5, "nutricionista", f_big, WHITE)
    y = draw_centered_text(draw, y + 5, "que te habla", f_big, WHITE)
    y = draw_centered_text(draw, y + 5, "como un amigo", f_big, ACCENT)

    draw.rounded_rectangle([(W // 2 - 60, y + 30), (W // 2 + 60, y + 38)], radius=4, fill=PRIMARY)

    # Sub
    draw_centered_text(draw, y + 80, "Y vos elegis su personalidad", f_body, MUTED)

    # Three personality tags
    tags = [
        ("Mentor", PRIMARY, 180),
        ("Challenger", RED_SOFT, 460),
        ("Amigo", GREEN, 740),
    ]
    tag_y = y + 170
    f_tag = get_font(28, bold=True)
    for name, color, tx in tags:
        bbox = draw.textbbox((0, 0), name, font=f_tag)
        tw = bbox[2] - bbox[0] + 40
        rounded_rect(draw, (tx - tw // 2, tag_y, tx + tw // 2, tag_y + 50), fill=color, radius=14)
        draw.text((tx - (bbox[2] - bbox[0]) // 2, tag_y + 10), name, font=f_tag, fill=WHITE)

    # Bottom
    draw_centered_text(draw, H - 120, "CoachKai", f_mid, PRIMARY)
    draw_centered_text(draw, H - 60, ">>>", f_mid, ACCENT)

    return img


def slide_2_personalities():
    """Show the 3 coach personalities."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (10, 10, 25), (10, 10, 15))

    f_title = get_font(48, bold=True)
    f_name = get_font(38, bold=True)
    f_body = get_font(30)
    f_emoji = get_font(56)

    draw_centered_text(draw, 80, "Elegis como te habla", f_title, WHITE)
    draw_centered_text(draw, 150, "3 personalidades, 1 coach", f_body, MUTED)

    coaches = [
        {
            "name": "Mentor",
            "color": PRIMARY,
            "icon": "~",
            "desc": "Tranquilo y educativo.\nTe explica todo con paciencia\ny te guia paso a paso.",
            "quote": "\"Buen registro! Sumale una fruta\ny llegas perfecto a tu objetivo.\"",
            "for_who": "Para los que quieren aprender",
        },
        {
            "name": "Challenger",
            "color": RED_SOFT,
            "icon": "!",
            "desc": "Directo y sin filtro.\nTe dice las cosas como son.\nTe exige pero te banca.",
            "quote": "\"No, boludo. Estas 246 kcal\npor encima. Dejalo asi\ny descansa.\"",
            "for_who": "Para los que necesitan un empujon",
        },
        {
            "name": "Amigo",
            "color": GREEN,
            "icon": ":)",
            "desc": "Copado y motivador.\nCelebra tus logros y te\nacompana con buena onda.",
            "quote": "\"Geniaaal! Re bien esa comida,\nseguii asi que la estas\nrompiendo!\"",
            "for_who": "Para los que quieren buena onda",
        },
    ]

    y = 260
    for c in coaches:
        # Card background
        rounded_rect(draw, (60, y, W - 60, y + 300), fill=BG_CARD, radius=22)

        # Color accent bar on left
        draw.rounded_rectangle([(60, y), (72, y + 300)], radius=4, fill=c["color"])

        # Name + badge
        draw.text((100, y + 20), c["name"], font=f_name, fill=c["color"])

        # Description
        desc_y = y + 70
        for line in c["desc"].split("\n"):
            draw.text((100, desc_y), line, font=f_body, fill=WHITE)
            desc_y += 36

        # Quote bubble
        quote_y = y + 185
        rounded_rect(draw, (100, quote_y, W - 100, y + 270), fill=(30, 30, 50), radius=14)
        qy = quote_y + 10
        for line in c["quote"].split("\n"):
            draw.text((120, qy), line, font=get_font(24), fill=MUTED)
            qy += 28

        y += 330

    return img


def slide_3_challenger_intro():
    """CHALLENGER intro - the star of the show."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (30, 5, 5), (10, 10, 15))

    f_title = get_font(52, bold=True)
    f_big = get_font(60, bold=True)
    f_body = get_font(34)
    f_small = get_font(28)
    f_quote = get_font(36, bold=True)

    # Top badge
    badge = "EL MAS ELEGIDO"
    bbox = draw.textbbox((0, 0), badge, font=f_small)
    bw = bbox[2] - bbox[0] + 50
    rounded_rect(draw, ((W - bw) // 2, 80, (W + bw) // 2, 130), fill=RED_SOFT, radius=20)
    draw.text(((W - bbox[2] + bbox[0]) // 2, 87), badge, font=f_small, fill=WHITE)

    # Title
    draw_centered_text(draw, 200, "El Challenger", f_big, RED_SOFT)
    draw_centered_text(draw, 290, "Tu amigo que te dice", f_title, WHITE)
    draw_centered_text(draw, 360, "las cosas como son", f_title, WHITE)

    # Big quote
    rounded_rect(draw, (80, 480, W - 80, 680), fill=BG_CARD, radius=22)
    draw.rounded_rectangle([(80, 480), (92, 680)], radius=4, fill=RED_SOFT)

    draw_centered_text(draw, 510, "\"No, boludo. Estas 246 kcal", f_quote, WHITE, max_width=800)
    draw_centered_text(draw, 560, "por encima ya. Dejalo asi", f_quote, WHITE, max_width=800)
    draw_centered_text(draw, 610, "y descansa.\"", f_quote, WHITE, max_width=800)

    # Traits
    traits = [
        ("Te dice la verdad", "sin vueltas ni excusas"),
        ("Te banca cuando la piloteas", "y te frena cuando te mandas"),
        ("Habla como vos", "argentino, directo, real"),
    ]

    y = 740
    for title, sub in traits:
        draw.text((140, y), "->", font=f_body, fill=RED_SOFT)
        draw.text((200, y), title, font=get_font(32, bold=True), fill=WHITE)
        draw.text((200, y + 40), sub, font=f_small, fill=MUTED)
        y += 100

    # Bottom
    draw_centered_text(draw, H - 200, "Como tener un amigo fitness", f_body, MUTED)
    draw_centered_text(draw, H - 140, "que te conoce y no te miente", f_body, MUTED)
    draw_centered_text(draw, H - 60, ">>>", get_font(42, bold=True), ACCENT)

    return img


def slide_4_challenger_chat():
    """WhatsApp chat mockup showing Challenger in action."""
    img = Image.new("RGB", (W, H), WA_BG)
    draw = ImageDraw.Draw(img)

    f_title = get_font(36, bold=True)
    f_small = get_font(24)
    f_chat = get_font(28)

    # Top label
    rounded_rect(draw, (250, 20, W - 250, 65), fill=RED_SOFT, radius=16)
    draw_centered_text(draw, 27, "MODO CHALLENGER", get_font(24, bold=True), WHITE)

    # WA Header
    y = 75
    y = draw_wa_header(draw, y, "Coach Kai", "modo challenger")
    y += 20

    # Chat conversation
    # User logs meal
    y = draw_wa_chat_bubble(draw, 80, y,
        "Almorce fideos con salsa bolognesa, plato mediano",
        f_chat, is_incoming=False, time_str="20:15")

    # Coach responds with log
    y = draw_wa_chat_bubble(draw, 80, y,
        "Fideos con salsa bolognesa, plato mediano  ~520 kcal  |  22g prot  |  68g carbos  |  15g grasa\n\nHoy: 2430 / 2821 kcal (te quedan ~391)",
        f_chat, is_incoming=True, time_str="20:20")

    # User says genial
    y = draw_wa_chat_bubble(draw, 80, y,
        "genial",
        f_chat, is_incoming=False, time_str="20:20")

    # Coach gives tough love summary
    y = draw_wa_chat_bubble(draw, 80, y,
        "Perfecto. Ya estas en 2430 kcal - 246 por encima de tu objetivo. Manana entrenas, asi que no es el fin del mundo, pero controlate.\n\nAlgo mas o cerramos el dia?",
        f_chat, is_incoming=True, time_str="20:20")

    # User asks for more
    y = draw_wa_chat_bubble(draw, 80, y,
        "me queda espacio para algo?",
        f_chat, is_incoming=False, time_str="20:23")

    # THE money shot - tough love response
    y = draw_wa_chat_bubble(draw, 80, y,
        "No, boludo. Estas 246 kcal por encima ya. Si comes algo mas, manana antes de entrenar te vas a sentir hinchado.\n\nDejalo asi y descansa. Manana a entrenar con hambre, que rinde mas.",
        f_chat, is_incoming=True, time_str="20:23")

    # Bottom caption
    rounded_rect(draw, (100, H - 110, W - 100, H - 30), fill=BG_CARD, radius=16)
    draw_centered_text(draw, H - 100, "Esto es una conversacion REAL con CoachKai", get_font(26, bold=True), ACCENT)

    return img


def slide_5_vs():
    """Challenger vs Nutricionista tradicional."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (15, 10, 30), (10, 10, 15))

    f_title = get_font(44, bold=True)
    f_head = get_font(32, bold=True)
    f_body = get_font(28)
    f_vs = get_font(56, bold=True)

    draw_centered_text(draw, 80, "Nutricionista clasico", f_title, MUTED)
    draw_centered_text(draw, 140, "vs CoachKai Challenger", f_title, RED_SOFT)

    # VS circle
    draw.ellipse([(W // 2 - 35, 210), (W // 2 + 35, 280)], fill=ACCENT)
    bbox = draw.textbbox((0, 0), "VS", font=f_head)
    draw.text((W // 2 - (bbox[2] - bbox[0]) // 2, 225), "VS", font=f_head, fill=WHITE)

    comparisons = [
        ("Nutri clasico", "CoachKai Challenger"),
        ("Te da un PDF y chau", "Te habla todos los dias"),
        ("Turno 1 vez al mes", "Disponible 24/7"),
        ("Te dice 'esta bien'", "Te dice 'no boludo, para'"),
        ("$30.000+/mes", "$8.999/mes"),
        ("Responde en 48hs", "Responde en 5 segundos"),
        ("Generico para todos", "Adaptado a VOS"),
    ]

    y = 320
    # Headers
    rounded_rect(draw, (60, y, 520, y + 50), fill=(40, 20, 20), radius=12)
    rounded_rect(draw, (540, y, W - 60, y + 50), fill=(20, 30, 20), radius=12)
    draw.text((80, y + 10), comparisons[0][0], font=f_head, fill=RED_SOFT)
    draw.text((560, y + 10), comparisons[0][1], font=f_head, fill=GREEN)
    y += 70

    for old, new in comparisons[1:]:
        # Divider
        draw.line([(60, y), (W - 60, y)], fill=(30, 30, 50), width=1)
        y += 15

        # X for old
        draw.text((80, y), "X", font=f_body, fill=RED_SOFT)
        draw.text((115, y), old, font=f_body, fill=MUTED)

        y += 45

        # Check for new
        draw.text((560, y - 45), "->", font=f_body, fill=GREEN)
        draw.text((600, y - 45), new, font=f_body, fill=WHITE)

        y += 25

    # Bottom
    draw_centered_text(draw, H - 130, "El futuro de la nutricion", f_body, MUTED)
    draw_centered_text(draw, H - 80, "ya esta en tu WhatsApp", f_body, ACCENT)

    return img


def slide_6_change():
    """Show you can change personality anytime."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (10, 15, 30), (10, 10, 15))

    f_title = get_font(48, bold=True)
    f_body = get_font(32)
    f_mid = get_font(36, bold=True)
    f_chat = get_font(28)

    draw_centered_text(draw, 80, "Lo mejor?", f_title, WHITE)
    draw_centered_text(draw, 150, "Cambias de coach cuando quieras", f_title, ACCENT)

    # Scenario cards
    scenarios = [
        {
            "when": "Lunes motivado",
            "coach": "Challenger",
            "color": RED_SOFT,
            "msg": "\"Dale pa, hoy no se negocia. A comer limpio.\"",
        },
        {
            "when": "Miercoles bajoneado",
            "coach": "Amigo",
            "color": GREEN,
            "msg": "\"Tranqui, un dia malo no arruina todo. Manana arrancas de cero!\"",
        },
        {
            "when": "Domingo curioso",
            "coach": "Mentor",
            "color": PRIMARY,
            "msg": "\"La proteina ayuda a la recuperacion muscular. Apunta a 1.8g/kg.\"",
        },
    ]

    y = 300
    for s in scenarios:
        # Card
        rounded_rect(draw, (70, y, W - 70, y + 240), fill=BG_CARD, radius=20)
        draw.rounded_rectangle([(70, y), (82, y + 240)], radius=4, fill=s["color"])

        # When
        draw.text((110, y + 18), s["when"], font=f_body, fill=MUTED)

        # Coach badge
        badge = s["coach"]
        bbox = draw.textbbox((0, 0), badge, font=get_font(24, bold=True))
        bw = bbox[2] - bbox[0] + 30
        rounded_rect(draw, (W - 70 - bw - 20, y + 15, W - 90, y + 50), fill=s["color"], radius=12)
        draw.text((W - 70 - bw - 5, y + 20), badge, font=get_font(24, bold=True), fill=WHITE)

        # Chat bubble inside card
        rounded_rect(draw, (110, y + 70, W - 110, y + 210), fill=(30, 30, 50), radius=16)
        msg_y = y + 85
        for line in s["msg"].split("\n"):
            # Word wrap for long lines
            words = line.split()
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                bb = draw.textbbox((0, 0), test, font=f_chat)
                if bb[2] - bb[0] > W - 280:
                    draw.text((135, msg_y), cur, font=f_chat, fill=WHITE)
                    msg_y += 34
                    cur = w
                else:
                    cur = test
            if cur:
                draw.text((135, msg_y), cur, font=f_chat, fill=WHITE)
                msg_y += 34

        y += 270

    # Command hint
    draw_centered_text(draw, H - 190, "Escribi /coach en WhatsApp", f_mid, WHITE)
    draw_centered_text(draw, H - 130, "y cambias al instante", f_body, MUTED)
    draw_centered_text(draw, H - 60, ">>>", get_font(42, bold=True), ACCENT)

    return img


def slide_7_cta():
    """CTA focused on trying the Challenger."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (35, 5, 15), (10, 10, 15))

    f_title = get_font(52, bold=True)
    f_big = get_font(58, bold=True)
    f_body = get_font(34)
    f_mid = get_font(38, bold=True)
    f_small = get_font(28)

    draw_centered_text(draw, 120, "Necesitas alguien que", f_title, WHITE)
    draw_centered_text(draw, 195, "te diga las cosas", f_title, WHITE)
    draw_centered_text(draw, 270, "como son?", f_title, RED_SOFT)

    # Big quote
    rounded_rect(draw, (100, 380, W - 100, 540), fill=BG_CARD, radius=22)
    draw.rounded_rectangle([(100, 380), (112, 540)], radius=4, fill=RED_SOFT)
    draw_centered_text(draw, 400, "\"Dejalo asi y descansa.", get_font(36, bold=True), WHITE, max_width=780)
    draw_centered_text(draw, 450, "Manana a entrenar con hambre,", get_font(36, bold=True), WHITE, max_width=780)
    draw_centered_text(draw, 500, "que rinde mas.\"", get_font(36, bold=True), WHITE, max_width=780)

    # Benefits
    benefits = [
        "7 dias GRATIS para probar",
        "Elegis tu personalidad de coach",
        "Directo en tu WhatsApp",
        "Sin apps, sin vueltas",
    ]

    y = 600
    for b in benefits:
        draw.text((170, y), "->", font=f_body, fill=GREEN)
        draw.text((230, y), b, font=f_body, fill=WHITE)
        y += 60

    # Price
    draw_centered_text(draw, 870, "Desde $8.999/mes", f_mid, ACCENT)
    draw_centered_text(draw, 920, "(menos que una consulta con un nutri)", f_small, MUTED)

    # CTA
    rounded_rect(draw, (120, 1010, W - 120, 1100), fill=RED_SOFT, radius=25)
    draw_centered_text(draw, 1025, "PROBAR EL CHALLENGER", f_mid, WHITE)

    rounded_rect(draw, (200, 1120, W - 200, 1190), fill=WA_GREEN, radius=20)
    draw_centered_text(draw, 1130, "Abrir WhatsApp >>>", f_body, WHITE)

    # Bottom
    draw_centered_text(draw, H - 90, "Link en la bio", f_mid, ACCENT)

    return img


# ── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    slides = [
        ("challenger_01_hook.png", slide_1_hook),
        ("challenger_02_personalidades.png", slide_2_personalities),
        ("challenger_03_intro.png", slide_3_challenger_intro),
        ("challenger_04_chat.png", slide_4_challenger_chat),
        ("challenger_05_vs.png", slide_5_vs),
        ("challenger_06_cambiar.png", slide_6_change),
        ("challenger_07_cta.png", slide_7_cta),
    ]

    for name, func in slides:
        img = func()
        path = os.path.join(OUT_DIR, name)
        img.save(path, "PNG", quality=95)
        print(f"  Saved: {path}")

    print(f"\nDone! {len(slides)} slides saved to {OUT_DIR}")
