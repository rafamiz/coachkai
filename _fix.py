import re

# ── Fix ai.py ────────────────────────────────────────────────────────────────
content = open('ai.py', encoding='utf-8').read()

# Fix 1: Update INTAKE_SYSTEM
old1 = (
    "When you have gathered sufficient, detailed information on ALL topics, call save_user_identity().\n\n"
    "Do not call it until you're confident you have a complete picture of the person."
)
new1 = (
    "IMPORTANT: Once you have the user's name, age (or rough estimate), weight, height, main goal, "
    "and activity level, call save_user_identity() IMMEDIATELY. Do not wait for perfect information. "
    "Estimates are fine. After 6 exchanges maximum, you MUST call save_user_identity() with whatever "
    "information you have collected so far.\n\n"
    "Do not keep the conversation going indefinitely. Collect the key info and save it."
)
if old1 in content:
    content = content.replace(old1, new1)
    print("Fix 1 applied OK")
else:
    print("Fix 1 NOT FOUND - searching for partial match...")
    idx = content.find("When you have gathered sufficient")
    print(f"  partial found at index: {idx}")
    if idx >= 0:
        print(repr(content[idx:idx+200]))

# Fix 3: Add force_extract_profile before onboarding_welcome
marker = "async def onboarding_welcome(name: str) -> str:"

force_extract = '''\
async def force_extract_profile(history: list) -> dict:
    """Force-extract a user profile from the conversation history."""
    global _turn_cost
    try:
        client = get_client()
        convo = "\\n".join(
            ("User" if m["role"] == "user" else "Bot") + ": " + m["content"]
            for m in history[-20:]
        )
        prompt = (
            "Based on this conversation, extract the user profile.\\n\\n" + convo + "\\n\\n"
            "Return a JSON object with: name (str), age (int or null), weight_kg (float or null), "
            "height_cm (float or null), goal (one of: lose_weight/gain_muscle/maintain/eat_healthier), "
            "activity_level (one of: sedentary/lightly_active/active/very_active), "
            "identity_markdown (str, 100+ word summary of the user). "
            "reply (str, a friendly closing message in Argentine Spanish). "
            "Only output valid JSON, nothing else."
        )
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        _turn_cost += resp.usage.input_tokens * _COST_INPUT + resp.usage.output_tokens * _COST_OUTPUT
        import json as _json, re as _re
        raw = resp.content[0].text.strip()
        match = _re.search(r\'\\{.*\\}\', raw, _re.DOTALL)
        if match:
            return _json.loads(match.group())
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ai] force_extract_profile error: {e}")
    return None


'''

if marker in content:
    content = content.replace(marker, force_extract + marker)
    print("Fix 3 applied OK")
else:
    print("Fix 3 marker NOT FOUND")

open('ai.py', 'w', encoding='utf-8').write(content)
print("ai.py saved")

# ── Fix handlers.py ──────────────────────────────────────────────────────────
hcontent = open('handlers.py', encoding='utf-8').read()

old2 = "    result = await ai.intake_turn(history, text)\n    logger.info(f\"[intake] result done={result.get('done')}, profile_name={result.get('profile', {}).get('name')}\")"
new2 = (
    "    result = await ai.intake_turn(history, text)\n"
    "    # Force completion if conversation is too long\n"
    "    if not result.get(\"done\") and len(history) >= 12:\n"
    "        logger.warning(f\"[intake] Max turns reached for {telegram_id}, forcing profile extraction\")\n"
    "        forced = await ai.force_extract_profile(history + [{\"role\": \"user\", \"content\": text}])\n"
    "        if forced:\n"
    "            result = {\"done\": True, \"profile\": forced, \"reply\": forced.get(\"reply\")}\n"
    "    logger.info(f\"[intake] result done={result.get('done')}, profile_name={result.get('profile', {}).get('name')}\")"
)

if old2 in hcontent:
    hcontent = hcontent.replace(old2, new2)
    print("Fix 2 applied OK")
else:
    print("Fix 2 NOT FOUND - searching...")
    idx = hcontent.find("result = await ai.intake_turn(history, text)")
    print(f"  intake_turn call at index: {idx}")
    if idx >= 0:
        print(repr(hcontent[idx:idx+300]))

open('handlers.py', 'w', encoding='utf-8').write(hcontent)
print("handlers.py saved")
