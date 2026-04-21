"""
Generate a 6-slide Instagram/TikTok carousel for CoachKai advertising.
Format: 1080x1350 (4:5 portrait, optimal for IG feed + TikTok).
Style: Dark premium with purple/indigo gradient accents.
"""

from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1350

# ── Colors ──────────────────────────────────────────────────────────────
BG_DARK = (10, 10, 15)
BG_CARD = (19, 19, 31)
PRIMARY = (99, 102, 241)      # indigo
ACCENT = (168, 85, 247)       # purple
GREEN = (34, 197, 94)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)
ORANGE = (251, 146, 60)
RED_SOFT = (239, 68, 68)


def get_font(size, bold=False):
    """Try to load a system font; fall back to default."""
    names = (
        ["arialbd.ttf", "Arial Bold.ttf", "segoeui.ttf"] if bold
        else ["arial.ttf", "Arial.ttf", "segoeui.ttf"]
    )
    for name in names:
        for base in [
            "C:/Windows/Fonts",
            "/usr/share/fonts/truetype/dejavu",
            "/System/Library/Fonts",
        ]:
            path = os.path.join(base, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    # absolute fallback
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()


def gradient_bg(draw, w, h, top_color, bot_color):
    """Draw a vertical linear gradient."""
    for y in range(h):
        ratio = y / h
        r = int(top_color[0] * (1 - ratio) + bot_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bot_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bot_color[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def rounded_rect(draw, xy, fill, radius=30):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_centered_text(draw, y, text, font, fill=WHITE, max_width=900):
    """Draw text centered horizontally, with simple word-wrap."""
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
    total_h = line_height * len(lines)
    cur_y = y

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        draw.text(((W - lw) // 2, cur_y), line, font=font, fill=fill)
        cur_y += line_height
    return cur_y


def draw_emoji_circle(draw, cx, cy, radius, emoji_text, font_big, bg_color):
    """Draw a colored circle with text inside (emoji placeholder)."""
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=bg_color
    )
    bbox = draw.textbbox((0, 0), emoji_text, font=font_big)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 5), emoji_text, font=font_big, fill=WHITE)


# ── Slide generators ────────────────────────────────────────────────────

def slide_1_hook():
    """HOOK: Attention grabber."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (15, 10, 40), (5, 5, 15))

    f_small = get_font(32)
    f_big = get_font(72, bold=True)
    f_mid = get_font(40, bold=True)
    f_body = get_font(34)

    # Top badge
    badge_text = "DESLIZA PARA VER"
    bbox = draw.textbbox((0, 0), badge_text, font=f_small)
    bw = bbox[2] - bbox[0] + 50
    rounded_rect(draw, ((W - bw) // 2, 100, (W + bw) // 2, 160), fill=ACCENT, radius=25)
    draw.text(((W - bbox[2] + bbox[0]) // 2, 108), badge_text, font=f_small, fill=WHITE)

    # Main text
    y = 300
    y = draw_centered_text(draw, y, "Comer bien", f_big, WHITE)
    y = draw_centered_text(draw, y + 10, "no tiene que", f_big, MUTED)
    y = draw_centered_text(draw, y + 10, "ser dificil", f_big, WHITE)

    # Accent line
    draw.rounded_rectangle(
        [(W // 2 - 60, y + 40), (W // 2 + 60, y + 48)],
        radius=4, fill=PRIMARY
    )

    # Sub
    y2 = y + 100
    draw_centered_text(draw, y2, "Tu coach de nutricion con IA", f_body, MUTED)
    draw_centered_text(draw, y2 + 60, "directo en WhatsApp", f_body, MUTED)

    # Bottom CTA arrow
    arrow = ">>>"
    bbox = draw.textbbox((0, 0), arrow, font=f_mid)
    draw.text(((W - bbox[2]) // 2, H - 180), arrow, font=f_mid, fill=ACCENT)

    # Brand
    draw_centered_text(draw, H - 100, "CoachKai", f_mid, PRIMARY)

    return img


def slide_2_problem():
    """PROBLEM: Pain points."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (20, 5, 10), (10, 10, 15))

    f_title = get_font(52, bold=True)
    f_body = get_font(36)
    f_emoji = get_font(56)

    draw_centered_text(draw, 120, "Te suena esto?", f_title, RED_SOFT)

    problems = [
        ("X", "No sabes cuantas calorias comes"),
        ("X", "Arrancas una dieta y la dejas a la semana"),
        ("X", "Pagas un nutricionista y te da un PDF generico"),
        ("X", "No tenes tiempo de planificar comidas"),
        ("X", "Queres resultados pero no sabes por donde empezar"),
    ]

    y = 320
    for icon, text in problems:
        # Red X circle
        draw.ellipse([100, y - 5, 150, y + 45], fill=RED_SOFT)
        bbox = draw.textbbox((0, 0), icon, font=f_body)
        draw.text((125 - (bbox[2] - bbox[0]) // 2, y), icon, font=f_body, fill=WHITE)

        # Text
        draw.text((180, y), text, font=f_body, fill=WHITE)
        y += 110

    # Bottom
    draw_centered_text(draw, H - 250, "Si te identificas con alguno...", f_body, MUTED)
    draw_centered_text(draw, H - 180, "tenes que ver esto >>>", f_body, ACCENT)

    return img


def slide_3_solution():
    """SOLUTION: What CoachKai does."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (5, 10, 30), (10, 10, 15))

    f_title = get_font(52, bold=True)
    f_body = get_font(34)
    f_big = get_font(42, bold=True)

    draw_centered_text(draw, 100, "Conoce CoachKai", f_title, PRIMARY)
    draw_centered_text(draw, 190, "Tu nutricionista con IA en WhatsApp", f_body, MUTED)

    features = [
        (GREEN, "01", "Manda una foto de tu comida", "y te dice calorias y macros al instante"),
        (PRIMARY, "02", "Plan personalizado", "adaptado a tu objetivo, peso y actividad"),
        (ACCENT, "03", "Coach 24/7 en WhatsApp", "preguntale lo que quieras, cuando quieras"),
        (ORANGE, "04", "Seguimiento diario", "te ayuda a mantener el habito"),
    ]

    y = 350
    for color, num, title, desc in features:
        # Number circle
        draw.ellipse([90, y, 150, y + 60], fill=color)
        bbox = draw.textbbox((0, 0), num, font=f_body)
        draw.text((120 - (bbox[2] - bbox[0]) // 2, y + 12), num, font=f_body, fill=WHITE)

        # Text
        draw.text((180, y + 2), title, font=f_big, fill=WHITE)
        draw.text((180, y + 55), desc, font=f_body, fill=MUTED)
        y += 140

    # Bottom
    rounded_rect(draw, (140, H - 200, W - 140, H - 120), fill=PRIMARY, radius=20)
    draw_centered_text(draw, H - 190, "Sin apps raras, solo WhatsApp", f_body, WHITE)

    return img


def slide_4_how():
    """HOW IT WORKS: 3 simple steps."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (10, 10, 25), (10, 10, 15))

    f_title = get_font(52, bold=True)
    f_num = get_font(80, bold=True)
    f_step = get_font(38, bold=True)
    f_desc = get_font(32)

    draw_centered_text(draw, 100, "Como funciona?", f_title, WHITE)
    draw_centered_text(draw, 180, "3 pasos simples", f_desc, MUTED)

    steps = [
        (PRIMARY, "1", "Sacale foto a tu comida", "O escribile que comiste"),
        (ACCENT, "2", "CoachKai analiza todo", "Calorias, proteina, carbos y grasas"),
        (GREEN, "3", "Te guia para mejorar", "Sugerencias personalizadas cada dia"),
    ]

    y = 340
    for color, num, title, desc in steps:
        # Big number
        draw.text((100, y - 10), num, font=f_num, fill=color)

        # Vertical line
        if num != "3":
            draw.line([(135, y + 90), (135, y + 170)], fill=(*color, 100), width=3)

        # Text
        draw.text((220, y + 5), title, font=f_step, fill=WHITE)
        draw.text((220, y + 55), desc, font=f_desc, fill=MUTED)
        y += 190

    # Chat mockup hint
    rounded_rect(draw, (120, H - 280, W - 120, H - 130), fill=BG_CARD, radius=20)
    draw.text((160, H - 260), "Tu:", font=f_desc, fill=MUTED)
    draw.text((220, H - 260), "\"Almorce milanesa con ensalada\"", font=f_desc, fill=WHITE)
    draw.text((160, H - 200), "Kai:", font=f_desc, fill=PRIMARY)
    draw.text((220, H - 200), "Genial! ~650 kcal, 42g prot", font=f_desc, fill=GREEN)

    return img


def slide_5_social_proof():
    """SOCIAL PROOF: Results & numbers."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, W, H, (5, 15, 10), (10, 10, 15))

    f_title = get_font(48, bold=True)
    f_big_num = get_font(72, bold=True)
    f_label = get_font(30)
    f_body = get_font(34)
    f_quote = get_font(32)

    draw_centered_text(draw, 100, "Resultados reales", f_title, GREEN)

    # Stats row
    stats = [
        ("12.8K+", "usuarios activos", GREEN),
        ("95%", "siguen despues\ndel primer mes", PRIMARY),
        ("4.9/5", "satisfaccion", ACCENT),
    ]

    x_positions = [130, 410, 720]
    for i, (num, label, color) in enumerate(stats):
        cx = x_positions[i]
        draw.text((cx, 280), num, font=f_big_num, fill=color)
        for j, line in enumerate(label.split("\n")):
            draw.text((cx, 365 + j * 35), line, font=f_label, fill=MUTED)

    # Testimonials
    testimonials = [
        ("Baje 8kg en 2 meses sin pasar hambre. Lo mejor es que le mando foto y listo.", "Lucia, 28"),
        ("Nunca pense que una IA me iba a ayudar tanto. Es como tener un nutri 24hs.", "Martin, 34"),
        ("Lo uso todos los dias. Super facil y los consejos son re buenos.", "Camila, 22"),
    ]

    y = 520
    for quote, author in testimonials:
        rounded_rect(draw, (80, y, W - 80, y + 170), fill=BG_CARD, radius=18)
        # Stars
        draw.text((120, y + 15), "* * * * *", font=f_label, fill=ORANGE)
        # Quote
        draw_centered_text(draw, y + 55, f'"{quote}"', f_quote, WHITE, max_width=800)
        # Author
        draw_centered_text(draw, y + 130, f"- {author}", f_label, MUTED)
        y += 200

    return img


def slide_6_cta():
    """CTA: Call to action."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Gradient from purple to dark
    gradient_bg(draw, W, H, (30, 10, 60), (10, 10, 15))

    f_title = get_font(58, bold=True)
    f_body = get_font(36)
    f_big = get_font(44, bold=True)
    f_small = get_font(30)
    f_price = get_font(64, bold=True)

    draw_centered_text(draw, 150, "Empeza hoy", f_title, WHITE)
    draw_centered_text(draw, 240, "7 dias GRATIS", f_title, GREEN)

    # Price card
    rounded_rect(draw, (120, 400, W - 120, 680), fill=BG_CARD, radius=25)

    # Old price strikethrough
    old_text = "$14.999/mes"
    bbox = draw.textbbox((0, 0), old_text, font=f_body)
    ox = (W - bbox[2] + bbox[0]) // 2
    draw.text((ox, 430), old_text, font=f_body, fill=MUTED)
    # Strikethrough line
    draw.line([(ox, 450), (ox + bbox[2] - bbox[0], 450)], fill=MUTED, width=2)

    # New price
    draw_centered_text(draw, 490, "$8.999/mes", f_price, WHITE)

    # Or annual
    draw_centered_text(draw, 590, "o $58.999/ano (ahorra 45%)", f_small, ACCENT)

    # Bullet benefits
    benefits = [
        "Coach IA 24/7 en WhatsApp",
        "Analisis de fotos de comida",
        "Plan personalizado a tu objetivo",
        "Seguimiento diario inteligente",
        "Cancela cuando quieras",
    ]

    y = 740
    for b in benefits:
        draw.text((160, y), "->", font=f_body, fill=GREEN)
        draw.text((220, y), b, font=f_body, fill=WHITE)
        y += 60

    # CTA Button
    rounded_rect(draw, (140, H - 280, W - 140, H - 190), fill=GREEN, radius=25)
    draw_centered_text(draw, H - 270, "EMPEZAR GRATIS >>>", f_big, WHITE)

    # Sub text
    draw_centered_text(draw, H - 150, "Sin tarjeta para la prueba gratis", f_small, MUTED)
    draw_centered_text(draw, H - 100, "Link en la bio", f_big, ACCENT)

    return img


# ── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    slides = [
        ("01_hook.png", slide_1_hook),
        ("02_problema.png", slide_2_problem),
        ("03_solucion.png", slide_3_solution),
        ("04_como_funciona.png", slide_4_how),
        ("05_resultados.png", slide_5_social_proof),
        ("06_cta.png", slide_6_cta),
    ]

    for name, func in slides:
        img = func()
        path = os.path.join(OUT_DIR, name)
        img.save(path, "PNG", quality=95)
        print(f"  Saved: {path}")

    print(f"\nDone! {len(slides)} slides saved to {OUT_DIR}")
