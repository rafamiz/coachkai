# NutriBot — Project Context

## Overview
Multi-user Telegram nutrition coach bot. Users send food photos or text meal descriptions. The bot analyzes meals with Claude AI (vision + text), tracks eating patterns, and sends smart follow-up messages.

## Tech Stack
- Python 3.10+
- python-telegram-bot v20+ (async, polling)
- Anthropic Claude API (claude-3-5-haiku-20241022) — meal analysis + vision
- APScheduler (AsyncIOScheduler) — background follow-up scheduling
- SQLite (nutribot.db) — local persistence
- python-dotenv — credentials

## File Structure
```
bot.py          — entry point, registers handlers, starts scheduler
handlers.py     — all Telegram event handlers (commands + messages + callbacks)
ai.py           — all Claude API calls (async)
db.py           — SQLite database layer (sync)
scheduler.py    — eating pattern learning + followup scheduler
requirements.txt
.env            — TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY
photos/         — downloaded user food photos
nutribot.db     — SQLite database (auto-created)
```

## Database Tables
- **users** — profile: telegram_id, name, age, weight_kg, height_cm, goal, activity_level, onboarding_complete
- **meals** — logged meals: user_id, telegram_id, description, photo_path, calories_est, meal_type, eaten_at, claude_analysis
- **followups** — sent follow-up messages log
- **eating_schedule** — learned avg meal times per user per meal_type (avg_hour, avg_minute, confidence, sample_count)

## Key Flows

### Onboarding (/start)
State machine in `context.user_data["onboarding_step"]`:
name → age → weight → height → goal (inline buttons) → activity (inline buttons) → done

### Meal Logging
- Photo → downloaded to photos/ → `ai.analyze_meal_photo()` (Claude vision)
- Text → `ai.analyze_meal_text()` (Claude text)
- Response includes: detected food, calories, alignment with goal, tip
- Saved to meals table, eating_schedule updated immediately

### Scheduler (APScheduler AsyncIOScheduler)
- Every 5 min: checks if any user has a meal reminder due (~30 min before avg meal time)
- Every 1 hour: recalculates avg meal times for all users
- Daily at 21:30: sends daily summary to users who logged meals
- Requires ≥3 meals of same type before calculating schedule, ≥30% confidence to send reminders

## Tone & Language
- Spanish rioplatense (Argentine), uses "vos" not "tú"
- Warm, encouraging, short messages, natural emojis
- Not preachy

## Commands
- /start — onboarding (or re-onboarding)
- /plan — personalized meal plan
- /stats — today's meal summary
- /reset — wipe profile and restart onboarding

## Running
```bash
pip install -r requirements.txt
python bot.py
```
