"""
nutrition_lookup.py - Search Open Food Facts for nutritional data.
Free, no API key required.
"""
import httpx
import logging

logger = logging.getLogger(__name__)

OPENFOODFACTS_URL = "https://world.openfoodfacts.org/cgi/search.pl"


async def search_food(query: str, country: str = "ar") -> dict | None:
    """
    Search Open Food Facts for a food item.
    Returns dict with calories, proteins, carbs, fats per 100g or None if not found.
    """
    try:
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 5,
            "fields": "product_name,nutriments,serving_size,brands",
            "tagtype_0": "countries",
            "tag_contains_0": "contains",
            "tag_0": "argentina",
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(OPENFOODFACTS_URL, params=params)
            data = resp.json()

        products = data.get("products", [])
        if not products:
            # Try without country filter
            params.pop("tagtype_0", None)
            params.pop("tag_contains_0", None)
            params.pop("tag_0", None)
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(OPENFOODFACTS_URL, params=params)
                data = resp.json()
            products = data.get("products", [])

        if not products:
            return None

        # Take the first product with nutritional data
        for product in products:
            n = product.get("nutriments", {})
            cal = n.get("energy-kcal_100g") or n.get("energy_100g", 0)
            if cal and float(cal) > 0:
                return {
                    "name": product.get("product_name", query),
                    "brand": product.get("brands", ""),
                    "calories_per_100g": float(cal),
                    "proteins_per_100g": float(n.get("proteins_100g", 0) or 0),
                    "carbs_per_100g": float(n.get("carbohydrates_100g", 0) or 0),
                    "fats_per_100g": float(n.get("fat_100g", 0) or 0),
                    "serving_size": product.get("serving_size", "100g"),
                }
        return None
    except Exception as e:
        logger.warning(f"[nutrition_lookup] search failed for '{query}': {e}")
        return None
