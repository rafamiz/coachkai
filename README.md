# NutriBot 🥗

Bot de Telegram que actúa como coach de nutrición personal. Analizá tus comidas con fotos o texto, recibí consejos personalizados y seguimiento de tus hábitos.

## Features

- **Onboarding conversacional** — el bot te conoce (nombre, edad, peso, altura, objetivo, actividad)
- **Análisis de fotos** — mandá una foto de tu plato y Claude lo analiza con visión artificial
- **Análisis de texto** — describí lo que comés y el bot estima calorías y calidad nutricional
- **Seguimiento inteligente** — aprende a qué hora comés y te manda recordatorios antes
- **Resumen diario** — un cierre del día con lo que comiste y cómo vas con tu objetivo
- **Plan personalizado** — plan de alimentación generado por IA según tu perfil

## Setup

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar credenciales en .env
TELEGRAM_BOT_TOKEN=tu_token_aqui
ANTHROPIC_API_KEY=tu_key_aqui

# 3. Correr el bot
python bot.py
```

## Comandos

| Comando | Descripción |
|---------|-------------|
| `/start` | Onboarding inicial (o volver a empezar) |
| `/plan` | Ver tu plan de alimentación personalizado |
| `/stats` | Resumen de comidas del día |
| `/reset` | Borrar perfil y empezar de cero |

## Uso

- **Foto de comida** → el bot la analiza automáticamente
- **Texto** → describí qué comiste ("comí un sándwich de pollo con ensalada")
- El bot responde con: detección, calorías estimadas, alineación con tu objetivo, tip

## Stack

- `python-telegram-bot` v20+ (async)
- `anthropic` SDK — Claude claude-3-5-haiku-20241022 (text + vision)
- `APScheduler` — seguimiento de horarios y recordatorios
- `SQLite` — base de datos local
