import asyncio
import logging
from io import BytesIO

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

QUICKCHART_URL = "https://quickchart.io/chart"

MEAL_TYPE_LABELS = {
    "breakfast": "Desayuno",
    "lunch": "Almuerzo",
    "dinner": "Cena",
    "snack": "Merienda",
}
MEAL_TYPES_ORDER = ["breakfast", "lunch", "dinner", "snack"]


def estimate_daily_calories(user: dict) -> int:
    weight = user.get("weight_kg") or 70
    height = user.get("height_cm") or 170
    age = user.get("age") or 30
    # Mifflin-St Jeor (gender-neutral average)
    bmr = 10 * weight + 6.25 * height - 5 * age
    activity_map = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
        "muy activo": 1.9,
        "moderado": 1.55,
        "ligero": 1.375,
        "sedentario": 1.2,
    }
    activity_key = (user.get("activity_level") or "moderate").lower()
    multiplier = activity_map.get(activity_key, 1.55)
    tdee = bmr * multiplier
    goal = (user.get("goal") or "maintain").lower()
    if any(w in goal for w in ("baj", "perder", "loss", "deficit")):
        tdee -= 500
    elif any(w in goal for w in ("sub", "ganar", "gain", "masa", "muscle")):
        tdee += 300
    return max(1200, int(tdee))


async def _fetch_chart(client: httpx.AsyncClient, config: dict, width: int, height: int) -> bytes:
    payload = {
        "chart": config,
        "width": width,
        "height": height,
        "backgroundColor": "#1e293b",
        "format": "png",
    }
    resp = await client.post(QUICKCHART_URL, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.content


def _build_doughnut_config(total_proteins: float, total_carbs: float, total_fats: float) -> dict:
    return {
        "type": "doughnut",
        "data": {
            "labels": ["Proteínas", "Carbos", "Grasas"],
            "datasets": [{
                "data": [round(total_proteins, 1), round(total_carbs, 1), round(total_fats, 1)],
                "backgroundColor": ["#22c55e", "#3b82f6", "#f59e0b"],
                "borderWidth": 0,
            }],
        },
        "options": {
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Macros del día (g)",
                    "color": "white",
                    "font": {"size": 14},
                },
                "legend": {
                    "labels": {"color": "white", "font": {"size": 11}},
                },
            },
            "cutout": "60%",
        },
    }


def _build_bar_config(cal_per_meal: dict, daily_goal: int) -> dict:
    labels = [MEAL_TYPE_LABELS[mt] for mt in MEAL_TYPES_ORDER]
    calories = [cal_per_meal.get(mt, 0) for mt in MEAL_TYPES_ORDER]
    goal_per_meal = round(daily_goal / 4)

    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Calorías",
                    "data": calories,
                    "backgroundColor": ["#22c55e", "#3b82f6", "#f59e0b", "#a855f7"],
                    "borderRadius": 6,
                },
                {
                    "label": "Meta por comida",
                    "data": [goal_per_meal] * 4,
                    "type": "line",
                    "borderColor": "#ef4444",
                    "borderDash": [6, 4],
                    "borderWidth": 2,
                    "pointRadius": 0,
                    "fill": False,
                },
            ],
        },
        "options": {
            "plugins": {
                "title": {
                    "display": True,
                    "text": f"Calorías por comida (meta: {daily_goal} kcal/día)",
                    "color": "white",
                    "font": {"size": 14},
                },
                "legend": {
                    "labels": {"color": "white", "font": {"size": 11}},
                },
            },
            "scales": {
                "y": {
                    "ticks": {"color": "white"},
                    "grid": {"color": "rgba(255,255,255,0.1)"},
                    "beginAtZero": True,
                },
                "x": {
                    "ticks": {"color": "white"},
                    "grid": {"color": "rgba(255,255,255,0.1)"},
                },
            },
        },
    }


async def generate_daily_summary_chart(user: dict, meals: list) -> bytes:
    """Generate a 600x350 PNG with a doughnut (macros) and bar (calories) chart side by side."""
    total_proteins = sum(m.get("proteins_g") or 0 for m in meals)
    total_carbs = sum(m.get("carbs_g") or 0 for m in meals)
    total_fats = sum(m.get("fats_g") or 0 for m in meals)

    cal_per_meal: dict[str, int] = {}
    for m in meals:
        mt = m.get("meal_type") or "snack"
        cal_per_meal[mt] = cal_per_meal.get(mt, 0) + (m.get("calories_est") or 0)

    daily_goal = estimate_daily_calories(user)

    doughnut_cfg = _build_doughnut_config(total_proteins, total_carbs, total_fats)
    bar_cfg = _build_bar_config(cal_per_meal, daily_goal)

    async with httpx.AsyncClient() as client:
        img1_bytes, img2_bytes = await asyncio.gather(
            _fetch_chart(client, doughnut_cfg, 300, 350),
            _fetch_chart(client, bar_cfg, 300, 350),
        )

    img1 = Image.open(BytesIO(img1_bytes)).convert("RGB")
    img2 = Image.open(BytesIO(img2_bytes)).convert("RGB")

    combined = Image.new("RGB", (600, 350), color="#1e293b")
    combined.paste(img1, (0, 0))
    combined.paste(img2, (300, 0))

    buf = BytesIO()
    combined.save(buf, format="PNG")
    return buf.getvalue()
