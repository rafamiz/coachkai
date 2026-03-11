import asyncio
import httpx

async def test_off(query):
    params = {
        "search_terms": query,
        "json": "1",
        "page_size": "3",
        "fields": "product_name,nutriments",
        "lang": "es"
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get("https://world.openfoodfacts.org/cgi/search.pl", params=params)
        data = resp.json()
    products = data.get("products", [])
    if not products:
        print(f"[{query}] NOT FOUND")
        return
    for p in products[:1]:
        n = p.get("nutriments", {})
        kcal = n.get("energy-kcal_100g") or n.get("energy_100g", 0)
        prot = n.get("proteins_100g", 0)
        name = p.get("product_name", "?")
        print(f"[{query}] '{name}' -> {kcal} kcal/100g, {prot}g prot")

async def main():
    foods = ["milanesa", "asado", "medialunas", "empanada", "pollo", "arroz", "pasta", "yogur", "banana", "huevo"]
    for f in foods:
        await test_off(f)
        await asyncio.sleep(0.3)

asyncio.run(main())
