# Fix: First WhatsApp message should send onboarding link

## Context
When a new user messages the bot for the first time, instead of doing onboarding via WhatsApp chat, 
send them a link to the web onboarding app.

## Change in whatsapp_handler.py

In the `_handle_onboarding` function, when `step is None` (brand new user), instead of starting
the chat-based onboarding, return this message:

```
Hola! Soy CoachKai, tu coach de nutrición personal 🤖

Para empezar, completá tu perfil en 2 minutos:
👉 https://coachkai-production.up.railway.app/onboarding

Ahí elegís tu objetivo, tus datos y el tipo de coach que querés.
Al final te cuento cómo funciona todo 💪
```

Also set onboarding_step to "awaiting_webapp" so we know they were sent the link.

## Also handle the case where they message again before completing onboarding
If step == "awaiting_webapp", send the same link again:
```
Todavía no completaste tu perfil. Entrá acá y listo:
👉 https://coachkai-production.up.railway.app/onboarding
```

## Note
- Keep all existing onboarding chat steps as fallback (in case webapp fails)
- Only change the initial step (step is None → send link instead of asking name)
- python not python3
