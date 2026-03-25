# NutriBot — Identity Mode + Mejoras

## 1. Identity Mode (coach personality)

### DB change
Add column to users table:
```sql
ALTER TABLE users ADD COLUMN coach_mode TEXT DEFAULT 'mentor';
```
Values: 'mentor' | 'roaster'

### Onboarding change (handlers.py)
After activity level step, add new step: ask coach mode
```
"Último paso: ¿qué tipo de coach querés?

🤝 *Mentor* — Te apoyo, celebro tus logros, te empujo con cariño
🔥 *Roaster* — Te digo las verdades sin filtro. Si la cagás, lo vas a saber."
```
Inline buttons: [🤝 Mentor] [🔥 Roaster]
Save to users.coach_mode

### Also add /coach command to change mode anytime
```
/coach → shows current mode + buttons to switch
```

### ai.py changes
In EVERY system prompt that generates a response to the user, add a section based on coach_mode:

**mentor system prompt addition:**
```
PERSONALIDAD: Sos un coach cálido y motivador. Usás "vos". Celebrás cada logro, por pequeño que sea. Cuando el usuario se equivoca, lo guiás con empatía. Nunca sos duro. Usás emojis con moderación. Sos como ese amigo que siempre te banca.
```

**roaster system prompt addition:**
```
PERSONALIDAD: Sos un coach despiadado pero que genuinamente quiere que el usuario mejore. Usás "vos". Cuando el usuario come mal o no cumple, lo destroys con humor ácido pero sin ser cruel. Ejemplos de tu estilo: "Tercera pizza esta semana. Impresionante la consistencia... lástima que sea para destruirte.", "Tu Apple Watch se avergüenza de estar en tu muñeca.", "2000 pasos hoy. Mi abuela hace más ejercicio y tiene 87 años." Cuando el usuario hace algo bien, lo reconocés brevemente pero siempre encontrás algo para empujar más. Nunca sos malo de verdad — sos el entrenador que nadie quiere pero que todos necesitan.
```

Functions to update:
- analyze_meal_photo() — pass coach_mode to system prompt
- analyze_meal_text() — pass coach_mode to system prompt  
- generate_meal_plan() — pass coach_mode
- generate_daily_summary() — pass coach_mode
- Any other function that generates user-facing text

## 2. Macro closing message (proactive end-of-day nudge)

In scheduler.py, add a new scheduled job:
- Runs at 19:00 every day
- For each user who has logged at least 1 meal today:
  - Calculate remaining calories/protein for the day
  - Send a message like: "Llevás 1200 cal hoy. Te quedan ~600 para llegar a tu meta. Perfecto para una pechuga con verduras." (mentor) OR "Llevás 1200 cal y todavía no cenaste. No me decepciones esta noche." (roaster)

## 3. Change coach reminder messages to use coach_mode too
In scheduler.py, meal reminder messages should also respect coach_mode.

## Implementation order
1. DB migration (add coach_mode column)
2. Update onboarding flow to ask coach mode
3. Add /coach command
4. Update all ai.py system prompts to accept + use coach_mode
5. Update scheduler.py for 19:00 macro nudge
6. Test both modes with a few sample messages

## Test
After implementing, run a quick simulation:
```python
# Test roaster mode
from ai import analyze_meal_text
import asyncio
result = asyncio.run(analyze_meal_text("comí una pizza entera", user_profile={...}, coach_mode="roaster"))
print(result)

# Test mentor mode
result = asyncio.run(analyze_meal_text("comí una pizza entera", user_profile={...}, coach_mode="mentor"))
print(result)
```

## Note
- python not python3
- Keep all existing functionality working
- Don't break the Telegram bot flow
- After implementing, commit: git add -A && git commit -m "feat: identity mode (mentor/roaster) + macro closing nudge"
- Then: openclaw system event --text "Done: NutriBot identity mode listo. Mentor y Roaster funcionando." --mode now
