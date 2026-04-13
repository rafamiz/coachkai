# NutriBot — Onboarding Web App (High-Conversion)

## Goal
Build a beautiful, mobile-first onboarding web app that collects user data, lets them choose their coach identity, and ends in a paywall. Optimized for conversion using consumer psychology principles.

## Tech Stack
- Single HTML file served by FastAPI at GET /onboarding
- Vanilla JS (no frameworks), inline CSS
- Mobile-first, works perfectly on phone
- Smooth slide transitions (CSS transforms)

## Conversion Psychology Principles to Apply
1. **Progress bar** — visible at top, fills as user advances (commitment bias)
2. **Personalization early** — ask name first, use it throughout ("Rafael, your plan is ready")
3. **Sunk cost** — the more they fill in, the more invested they feel
4. **Identity framing** — "Choose your coach" not "choose a plan"
5. **Result preview before paywall** — show them their personalized calorie target BEFORE asking for payment
6. **Social proof** — "12,847 people already hitting their goals with CoachKai"
7. **Urgency** — "Your personalized plan is ready" feeling
8. **Reduction of friction** — big tap targets, no typing when possible (use buttons)
9. **Emotional hook on paywall** — connect to their stated goal, not features

## Slides (in order)

### Slide 1 — Hook
- Full-screen gradient background (dark purple to blue)
- Logo: "CoachKai 🤖"
- Big headline: "Tu coach de nutrición personal por WhatsApp"
- Subtext: "Foto de tu comida → 10 segundos → calorías, proteínas, y qué comer en tu próxima comida"
- Big CTA button: "Empezar gratis →"
- Small text: "12,847 personas ya cumpliendo sus metas"

### Slide 2 — Name
- "¿Cómo te llamamos?"
- Text input, large font
- Keyboard shows automatically
- Continue button activates when user types

### Slide 3 — Goal (after name, use name in text)
- "{name}, ¿cuál es tu objetivo principal?"
- 3 big cards with emoji + text:
  - 🔥 Bajar de peso
  - 💪 Ganar músculo
  - ⚖️ Mantenerme
- Tap to select, auto-advances

### Slide 4 — Activity level
- "¿Cuánto te movés?"
- 4 cards:
  - 🛋️ Poco (trabajo sentado, sin ejercicio)
  - 🚶 Algo (1-3 días por semana)
  - 🏃 Bastante (4-5 días)
  - 🏋️ Mucho (entreno intenso 6-7 días)
- Tap to select, auto-advances

### Slide 5 — Body stats
- "{name}, necesitamos tus datos para calcular tu plan exacto"
- 3 inputs in a row: Edad / Peso (kg) / Altura (cm)
- Number inputs, numeric keyboard on mobile
- Continue button

### Slide 6 — Coach identity (KEY SLIDE — this is the differentiator)
- "Elegí tu coach"
- 2 big cards side by side, each with personality description:

  Card A — "El Mentor 🤝"
  > "Te celebro cada logro. Te guío con empatía cuando te equivocás. Estoy para bancarte."
  > Tag: "Popular entre principiantes"

  Card B — "El Challenger 🔥"
  > "Sin filtros. Si la cagás, lo vas a saber. Resultados reales requieren verdades reales."
  > Tag: "Para los que van en serio"

- Selecting a card gives it a glow/border effect
- Large CTA: "Este es mi coach →"

### Slide 7 — Calculating (animated, fake loading for 2.5 seconds)
- Spinner / animated bars
- Text cycling through:
  - "Calculando tu metabolismo basal..."
  - "Ajustando para tu nivel de actividad..."
  - "Generando tu plan personalizado..."
- Auto-advances after 2.5s

### Slide 8 — Results preview (BEFORE paywall — crucial)
- Big card with calculated stats:
  - "Tu objetivo calórico: **1,850 kcal/día**"
  - "Proteínas: **145g** | Carbos: **190g** | Grasas: **65g**"
- Below: "Tu plan incluye..."
  - ✅ Análisis de fotos de comida en segundos
  - ✅ Coach personal por WhatsApp 24/7
  - ✅ Resumen diario automático
  - ✅ Plan de comidas semanal
  - ✅ Recordatorios inteligentes
- CTA: "Ver mi plan completo →"

### Slide 9 — Paywall
- "{name}, tu plan está listo 🎉"
- Price card with slight shadow:
  - ~~$15 USD/mes~~
  - **$9 USD/mes** (precio de lanzamiento)
  - "Cancelá cuando quieras"
- Urgency: "Precio de lanzamiento — disponible para los primeros 500 usuarios"
- Big button: "Empezar ahora →" (links to WhatsApp with pre-filled message)
- Small below: "O probá 7 días gratis →" (also links to WhatsApp)
- Social proof: ⭐⭐⭐⭐⭐ "Los usuarios pierden en promedio 2.3kg en su primer mes"

## WhatsApp pre-fill link
When user clicks paywall CTA, open:
```
https://wa.me/14155238886?text=Hola!%20Quiero%20empezar%20con%20CoachKai
```

## Calculated stats (client-side, rough Mifflin-St Jeor)
```javascript
function calcCalories(age, weight, height, goal, activity) {
  // BMR
  let bmr = 10 * weight + 6.25 * height - 5 * age + 5; // male (simplify)
  const activityMultipliers = { sedentary: 1.2, lightly: 1.375, active: 1.55, very: 1.725 };
  let tdee = bmr * (activityMultipliers[activity] || 1.375);
  if (goal === 'lose') tdee -= 400;
  if (goal === 'gain') tdee += 300;
  return Math.round(tdee);
}
```

## Visual Design
- Background: deep dark (#0a0a0f) with purple gradient accents
- Cards: dark (#13131f) with border (#2a2a40)
- Primary color: #6366f1 (indigo)
- Accent: #a855f7 (purple)
- Text: white / #94a3b8
- Font: Inter (Google Fonts)
- Progress bar: thin line at top, indigo fill
- Slide transition: translateX with ease-in-out 300ms
- Card selection: glowing border + scale(1.02)

## FastAPI route
In main.py add:
```python
from fastapi.responses import HTMLResponse

@app.get("/onboarding")
def onboarding():
    with open("onboarding.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())
```

## Files to create
- `onboarding.html` — the full webapp
- Update `main.py` to serve it

## After building
1. Test by opening http://localhost:8000/onboarding
2. Check mobile view in DevTools
3. git add -A && git commit -m "feat: high-conversion onboarding webapp"
4. git push origin master
5. Also push to main: git push origin master:main
6. openclaw system event --text "Done: CoachKai onboarding webapp lista. URL: https://coachkai-production.up.railway.app/onboarding" --mode now
