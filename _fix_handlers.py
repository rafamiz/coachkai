import re

content = open(r'C:\Users\T14s\Projects\nutribot\handlers.py', encoding='utf-8').read()

# 1. Add logging before/after the main ai.intake_turn call
old1 = '    result = await ai.intake_turn(history, text)\n\n    if result.get("done"):'
new1 = (
    '    logger.info(f"[intake] turn for {telegram_id}, history_len={len(history)}")\n'
    '    result = await ai.intake_turn(history, text)\n'
    '    logger.info(f"[intake] result done={result.get(\'done\')}, profile_name={result.get(\'profile\', {}).get(\'name\')}")\n'
    '\n'
    '    if result.get("done"):'
)

if old1 in content:
    content = content.replace(old1, new1)
    print('Step 1 OK - logging added')
else:
    print('Step 1 FAILED - pattern not found')

# 2. Replace the profile save block with try/except
old2 = '''    if result.get("done"):
        profile = result.get("profile", {})
        db.upsert_user(
            telegram_id,
            onboarding_complete=1,
            name=profile.get("name"),
            age=profile.get("age"),
            weight_kg=profile.get("weight_kg"),
            height_cm=profile.get("height_cm"),
            goal=profile.get("goal"),
            activity_level=profile.get("activity_level"),
        )
        if profile.get("identity_markdown"):
            db.save_profile_text(telegram_id, profile["identity_markdown"])'''

new2 = '''    if result.get("done"):
        profile = result.get("profile", {})
        try:
            db.upsert_user(
                telegram_id,
                onboarding_complete=1,
                name=profile.get("name"),
                age=profile.get("age"),
                weight_kg=profile.get("weight_kg"),
                height_cm=profile.get("height_cm"),
                goal=profile.get("goal"),
                activity_level=profile.get("activity_level"),
            )
            logger.info(f"[intake] Profile saved for {telegram_id}: onboarding_complete=1")
            if profile.get("identity_markdown"):
                db.save_profile_text(telegram_id, profile["identity_markdown"])
        except Exception as e:
            logger.error(f"[intake] FAILED to save profile for {telegram_id}: {e}", exc_info=True)
            await update.message.reply_text(
                "Hubo un error guardando tu perfil. Intent\u00e1 /start de nuevo."
            )
            return'''

if old2 in content:
    content = content.replace(old2, new2)
    print('Step 2 OK - try/except added')
else:
    print('Step 2 FAILED - pattern not found')
    # Debug: show the actual block
    idx = content.find('    if result.get("done"):')
    print('Found block at:', idx)
    print(repr(content[idx:idx+500]))

open(r'C:\Users\T14s\Projects\nutribot\handlers.py', 'w', encoding='utf-8').write(content)
print('File written.')
