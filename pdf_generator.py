"""
pdf_generator.py — Generate branded NUTRIMATE meal plan PDFs.
Uses reportlab (pure Python, no system deps needed).
"""
from io import BytesIO
from datetime import date

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# NUTRIMATE brand colors
TEAL = HexColor("#2d9d8f") if REPORTLAB_AVAILABLE else None
TEAL_LIGHT = HexColor("#e8f5f3") if REPORTLAB_AVAILABLE else None
DARK = HexColor("#2c3e50") if REPORTLAB_AVAILABLE else None
GRAY = HexColor("#7f8c8d") if REPORTLAB_AVAILABLE else None
BG = HexColor("#f8fffe") if REPORTLAB_AVAILABLE else None

GOAL_LABELS = {
    "lose_weight": "Bajar de peso",
    "gain_muscle": "Ganar músculo",
    "maintain": "Mantener peso",
    "eat_healthier": "Comer más sano",
}
ACTIVITY_LABELS = {
    "sedentary": "Sedentario",
    "lightly_active": "Poco activo",
    "light": "Poco activo",
    "moderate": "Moderado",
    "active": "Activo",
    "very_active": "Muy activo",
}


def generate_plan_pdf(user: dict, plan_text: str) -> bytes:
    """
    Generate a branded NUTRIMATE PDF with the meal plan.
    Returns PDF as bytes.
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab not installed. Run: pip install reportlab")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=1.5*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "NMTitle",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=TEAL,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    tagline_style = ParagraphStyle(
        "NMTagline",
        fontName="Helvetica",
        fontSize=10,
        textColor=GRAY,
        alignment=TA_LEFT,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "NMSection",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=TEAL,
        spaceBefore=16,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "NMBody",
        fontName="Helvetica",
        fontSize=10,
        textColor=DARK,
        leading=16,
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "NMSmall",
        fontName="Helvetica",
        fontSize=9,
        textColor=GRAY,
        alignment=TA_RIGHT,
    )
    user_label_style = ParagraphStyle(
        "NMUserLabel",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=DARK,
    )
    user_value_style = ParagraphStyle(
        "NMUserValue",
        fontName="Helvetica",
        fontSize=10,
        textColor=GRAY,
    )

    elements = []

    # ── Header ────────────────────────────────────────────────────────────────
    # Logo area (text-based since no image embedding needed)
    header_data = [[
        Paragraph("🌿 NUTRIMATE", title_style),
        Paragraph(date.today().strftime("%-d de %B, %Y") if hasattr(date.today(), "strftime") else str(date.today()), small_style),
    ]]
    header_table = Table(header_data, colWidths=[13*cm, 4*cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "BOTTOM"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    elements.append(header_table)
    elements.append(Paragraph("Tu compañero inteligente de nutrición", tagline_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=TEAL, spaceAfter=16))

    # ── User profile box ─────────────────────────────────────────────────────
    elements.append(Paragraph("👤 Perfil", section_style))

    goal = GOAL_LABELS.get(user.get("goal", ""), user.get("goal", "—"))
    activity = ACTIVITY_LABELS.get(user.get("activity_level", ""), user.get("activity_level", "—"))

    profile_data = [
        ["Nombre", user.get("name", "—"), "Objetivo", goal],
        ["Edad", f"{user.get('age', '—')} años", "Actividad", activity],
        ["Peso", f"{user.get('weight_kg', '—')} kg", "Altura", f"{user.get('height_cm', '—')} cm"],
    ]
    profile_table = Table(
        [[Paragraph(str(cell), user_label_style if i % 2 == 0 else user_value_style)
          for i, cell in enumerate(row)]
         for row in profile_data],
        colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 5*cm],
    )
    profile_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), TEAL_LIGHT),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [TEAL_LIGHT, white]),
        ("GRID", (0,0), (-1,-1), 0.5, HexColor("#d0ebe8")),
        ("PADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    elements.append(profile_table)

    # ── Meal Plan ────────────────────────────────────────────────────────────
    elements.append(Paragraph("🥗 Plan de Alimentación Personalizado", section_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor("#d0ebe8"), spaceAfter=8))

    # Parse and format the plan text
    for line in plan_text.split("\n"):
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 4))
            continue
        # Bold headers (lines starting with emoji or **)
        if line.startswith("**") and line.endswith("**"):
            clean = line.strip("*").strip()
            elements.append(Paragraph(f"<b>{clean}</b>", ParagraphStyle(
                "bold", parent=body_style, textColor=DARK, spaceBefore=8,
            )))
        elif line.startswith("#"):
            clean = line.lstrip("#").strip()
            elements.append(Paragraph(f"<b>{clean}</b>", section_style))
        elif line.startswith("•") or line.startswith("-"):
            clean = line.lstrip("•-").strip()
            elements.append(Paragraph(f"• {clean}", ParagraphStyle(
                "bullet", parent=body_style, leftIndent=12,
            )))
        else:
            # Render inline bold (**text**)
            import re
            formatted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
            formatted = re.sub(r'\*(.+?)\*', r'<i>\1</i>', formatted)
            elements.append(Paragraph(formatted, body_style))

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor("#d0ebe8")))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "Este plan fue generado por NUTRIMATE · No reemplaza la consulta con un profesional de la salud.",
        ParagraphStyle("footer", parent=small_style, alignment=TA_CENTER, fontSize=8, textColor=GRAY)
    ))

    doc.build(elements)
    return buf.getvalue()
