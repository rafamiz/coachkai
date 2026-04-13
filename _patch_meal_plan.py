# -*- coding: utf-8 -*-
"""Patch generate_meal_plan in ai.py"""
import re

content = open('ai.py', encoding='utf-8').read()

func_start = content.find('async def generate_meal_plan')
func_end = content.find('\nPROCESS_SYSTEM', func_start)
assert func_start != -1 and func_end != -1, "Markers not found"

new_func = (
    'async def generate_meal_plan(user: dict) -> dict:\n'
    '    """Returns dict with plan_text and meal_options (breakfasts, lunches, dinners)."""\n'
    '    profile = (\n'
    "        f\"Nombre: {user.get('name','?')}, Edad: {user.get('age','?')} a\u00f1os, \"\n"
    "        f\"Peso: {user.get('weight_kg','?')} kg, Altura: {user.get('height_cm','?')} cm, \"\n"
    "        f\"Objetivo: {user.get('goal','?')}, Actividad: {user.get('activity_level','?')}\"\n"
    '    )\n'
    '\n'
    '    if user.get("daily_calories"):\n'
    "        profile += f\", Calor\u00edas diarias objetivo: {user['daily_calories']} kcal\"\n"
    '\n'
    '    profile_text = user.get("profile_text", "")\n'
    '    if profile_text:\n'
    '        profile += "\\n\\nPerfil detallado:\\n" + profile_text[:500]\n'
    '\n'
    '    raw = await _ask([{\n'
    '        "role": "user",\n'
    '        "content": (\n'
    '            "Gener\u00e1 un plan de alimentaci\u00f3n personalizado para:\\n" + profile + "\\n\\n"\n'
    '            "Respond\u00e9 SOLO con JSON v\u00e1lido con esta estructura exacta (sin markdown, sin texto extra):\\n"\n'
    '            "{\\n"\n'
    '            \'  "calories": 2000,\\n\'\n'
    '            \'  "protein_g": 150,\\n\'\n'
    '            \'  "carbs_g": 200,\\n\'\n'
    '            \'  "fat_g": 65,\\n\'\n'
    '            \'  "summary": "Resumen breve del plan (2-3 oraciones)",\\n\'\n'
    '            \'  "tips": ["tip 1", "tip 2", "tip 3"],\\n\'\n'
    '            \'  "breakfasts": ["Opci\u00f3n 1 con porciones", "Opci\u00f3n 2", "Opci\u00f3n 3"],\\n\'\n'
    '            \'  "lunches": ["Opci\u00f3n 1 con porciones", "Opci\u00f3n 2", "Opci\u00f3n 3"],\\n\'\n'
    '            \'  "dinners": ["Opci\u00f3n 1 con porciones", "Opci\u00f3n 2", "Opci\u00f3n 3"],\\n\'\n'
    '            \'  "snacks": ["Snack 1", "Snack 2"]\\n\'\n'
    '            "}\\n"\n'
    '            "Las opciones deben ser espec\u00edficas, con porciones aproximadas. Respond\u00e9 SOLO el JSON, sin ning\u00fan texto antes o despu\u00e9s."\n'
    '        )\n'
    '    }])\n'
    '\n'
    '    import json, re\n'
    '\n'
    '    try:\n'
    '        # Strip markdown code fences if present\n'
    '        cleaned = re.sub(r"^```(?:json)?\\s*", "", raw.strip(), flags=re.IGNORECASE)\n'
    '        cleaned = re.sub(r"\\s*```$", "", cleaned)\n'
    '        # Extract JSON object\n'
    '        match = re.search(r\'\\{.*\\}\', cleaned, re.DOTALL)\n'
    '        if match:\n'
    '            return json.loads(match.group())\n'
    '    except Exception:\n'
    '        pass\n'
    '\n'
    '    # Fallback\n'
    '    return {\n'
    '        "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,\n'
    '        "summary": raw, "tips": [],\n'
    '        "breakfasts": [], "lunches": [], "dinners": [], "snacks": []\n'
    '    }\n'
    '\n'
)

new_content = content[:func_start] + new_func + content[func_end:]
open('ai.py', 'w', encoding='utf-8').write(new_content)
print("Patched successfully,", len(new_content), "bytes")
