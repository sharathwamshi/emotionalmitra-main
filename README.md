# Emotion Companion Bot

A simple text + voice chatbot that listens to how someone is feeling and responds
with empathy, using Anthropic's Claude for the conversation and Azure Speech for
the spoken reply. No database — everything is stored in JSON files under `data/`.

## How it works

- **Text input**: type in the box and hit Enter / the send button.
- **Voice input**: click the mic button. This uses the browser's own built-in
  speech recognition (Chrome/Edge), so no server-side audio handling is needed.
  The recognized text is sent to the bot just like a typed message.
- **Voice output**: every bot reply is also converted to speech via Azure's
  Text-to-Speech REST API and played automatically in the browser.
- **Safety net**: if a message contains language suggesting self-harm or
  suicidal thoughts, the bot always responds with crisis helpline numbers
  (India: AASRA, iCall, KIRAN) instead of a generic AI reply — this check
  happens in the backend, not the model, so it can't be skipped.
- **Storage**: `data/conversations.json` holds every session's transcript.
  `data/settings.json` holds the bot name, system prompt, and Azure voice name
  (all editable from the admin panel). Both files are created automatically on
  first run.

## Setup

```bash
cd emotion-companion-bot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and fill in:
- `ANTHROPIC_API_KEY` — your Anthropic key
- `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` — from your Azure Speech resource
  (Azure Portal → your Speech resource → "Keys and Endpoint")
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — the one admin login
- `FLASK_SECRET_KEY` — any random string

## Run

```bash
python app.py
```

Then open:
- `http://localhost:5000/` — the chatbot
- `http://localhost:5000/admin/login` — admin panel (view all conversations,
  edit bot name / system prompt / Azure voice, and log out)

## Notes / things to harden before real users touch this

- Passwords are compared in plain text and stored in `.env` — fine for an
  internal demo, but move to a hashed password and a proper user store before
  any real deployment.
- `conversations.json` will grow forever; add rotation/archiving if this runs
  long-term.
- The crisis-keyword list is intentionally basic — treat it as a safety net,
  not a substitute for a properly designed escalation flow if this becomes a
  real product.
- Azure voice names: browse the full neural voice list in the Azure docs and
  set `voice_name` in Settings to whichever fits (e.g. `en-IN-NeerjaNeural`,
  `hi-IN-SwaraNeural` for Hindi, etc.).
