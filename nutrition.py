"""
nutrition.py — Open Food Facts integration for accurate nutritional data.
Free API, no auth needed. https://world.openfoodfacts.org
"""

import re
import httpx

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"


async def lookup_food(query: str) -> dict | None:
    """
    Search Open Food Facts for a food item.
    Returns per-100g nutritional data or None if not found.
    """
    params = {
        "search_terms": query,
        "json": "1",
        "page_size": "5",
        "fields": "product_name,nutriments,serving_size",
        "lang": "es",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OFF_SEARCH_URL, params=params)
            data = resp.json()
    except Exception:
        return None

    products = data.get("products", [])
    if not products:
        return None

    # Pick the first product with nutriment data
    for product in products:
        n = product.get("nutriments", {})
        kcal = n.get("energy-kcal_100g") or n.get("energy_100g", 0)
        if kcal and float(kcal) > 0:
            return {
                "name": product.get("product_name", query),
                "kcal_per_100g": float(kcal),
                "proteins_per_100g": float(n.get("proteins_100g", 0)),
                "carbs_per_100g": float(n.get("carbohydrates_100g", 0)),
                "fats_per_100g": float(n.get("fat_100g", 0)),
            }
    return None


def parse_grams(portion_text: str) -> float | None:
    """
    Extract grams from a portion description.
    Examples: '200g', 'un plato (300g)', '1 taza ~250g' → 200, 300, 250
    """
    match = re.search(r"(\d+(?:\.\d+)?)\s*g\b", portion_text.lower())
    if match:
        return float(match.group(1))
    return None


def estimate_grams(portion_text: str) -> float:
    """
    Estimate grams from natural language portions when no explicit weight given.
    """
    text = portion_text.lower()
    estimates = {
        "grande": 300, "mediano": 200, "chico": 120, "pequeño": 120,
        "plato": 250, "taza": 200, "vaso": 200, "porcion": 150,
        "porción": 150, "rodaja": 80, "rebanada": 30, "lonja": 40,
        "unidad": 100, "pieza": 100, "filete": 150, "milanesa": 150,
    }
    for word, grams in estimates.items():
        if word in text:
            return grams
    return 150  # default fallback


async def get_nutrition_for_meal(food_name: str, portion_description: str) -> dict | None:
    """
    Look up nutritional data for a food and calculate for the given portion.
    Returns calculated macros or None if food not found in database.
    """
    food_data = await lookup_food(food_name)
    if not food_data:
        return None

    grams = parse_grams(portion_description)
    if grams is None:
        grams = estimate_grams(portion_description)

    factor = grams / 100.0
    return {
        "source": "open_food_facts",
        "food_name": food_data["name"],
        "grams": grams,
        "calories": round(food_data["kcal_per_100g"] * factor),
        "proteins_g": round(food_data["proteins_per_100g"] * factor, 1),
        "carbs_g": round(food_data["carbs_per_100g"] * factor, 1),
        "fats_g": round(food_data["fats_per_100g"] * factor, 1),
    }
