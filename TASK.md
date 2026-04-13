# Task: Add global cooldown between proactive messages in nutribot

## Problem
The scheduler sends multiple proactive messages in a short window because each job
acts independently without knowing others already sent something.
Example: check_proactive_messages, breakfast_checkin, and check_training_reminders
all fire around 8:30am sending 3 messages back-to-back.

## Solution: Global proactive message cooldown per user

Add a cooldown mechanism: if ANY proactive message was sent to a user in the last 45 minutes,
skip the next proactive message for that user.

### Implementation in db.py
Add column `last_proactive_sent` TIMESTAMP to users table:
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_proactive_sent TIMESTAMP;
```

Add two functions:
```python
def get_last_proactive_sent(telegram_id: int):
    """Returns datetime of last proactive message sent, or None."""
    ...

def update_last_proactive_sent(telegram_id: int):
    """Updates last_proactive_sent to now() for the user."""
    ...
```

### Implementation in scheduler.py
Add a helper function at the top:
```python
PROACTIVE_COOLDOWN_MINUTES = 45

async def _can_send_proactive(telegram_id: int) -> bool:
    """Returns True if enough time has passed since last proactive message."""
    last = db.get_last_proactive_sent(telegram_id)
    if last is None:
        return True
    import pytz
    from datetime import datetime, timedelta
    BA_TZ = pytz.timezone("America/Argentina/Buenos_Aires")
    now = datetime.now(BA_TZ)
    if last.tzinfo is None:
        last = BA_TZ.localize(last)
    return (now - last) >= timedelta(minutes=PROACTIVE_COOLDOWN_MINUTES)
```

Wrap ALL proactive send calls with this check:
- check_proactive_messages: check before sending
- send_meal_checkin (breakfast, lunch, snack, dinner): check before sending  
- check_training_reminders: check before sending
- send_inactivity_checkin: check before sending
- check_meal_absence: check before sending

When a proactive message IS sent, call `db.update_last_proactive_sent(telegram_id)`.

## Rules
- \uXXXX escapes for ALL accented chars in new string literals
- All file I/O: open(..., encoding='utf-8')
- python not python3
- Surgical edits only — don't rewrite whole functions unnecessarily

## Verification
python -c "import ast; [ast.parse(open(f,encoding='utf-8').read()) or print(f,'OK') for f in ['scheduler.py','db.py']]"

## Git
- git add scheduler.py db.py
- git commit -m "fix: add 45min global cooldown between proactive messages per user"
- git push origin master
- git push origin master:main --force
- git push nutribot master

## Notify
openclaw system event --text "Done: proactive message cooldown added to nutribot scheduler" --mode now
