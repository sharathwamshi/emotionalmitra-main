import os
import json
import uuid
import base64
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, session, render_template, redirect, url_for
import requests
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONV_FILE = os.path.join(DATA_DIR, "conversations.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

DEFAULT_SETTINGS = {
    "bot_name": "Mitra",
    "system_prompt": (
        "You are Mitra, a warm, empathetic companion. Someone is sharing how they feel "
        "with you. Respond with genuine warmth, validate their feelings, ask a gentle "
        "follow-up question, and keep your reply short (3-5 sentences) so it sounds "
        "natural when spoken aloud. You are not a therapist and cannot diagnose. If the "
        "person seems to be in serious distress, gently encourage them to reach out to "
        "a mental health professional or a trusted person in their life, in addition to "
        "talking with you."
    ),
    "voice_name": "en-IN-NeerjaNeural",
}

# Basic safety net: if any of these appear, we always surface crisis resources,
# regardless of what the model would otherwise generate.
CRISIS_KEYWORDS = [
    "kill myself", "end my life", "want to die", "suicide", "suicidal",
    "self harm", "self-harm", "hurt myself", "no reason to live", "better off dead",
]

CRISIS_MESSAGE = (
    "I'm really glad you told me this, and I want you to be safe. I'm not able to "
    "give the kind of help you need right now, but you deserve support from people "
    "who can be there with you directly. In India you can reach AASRA at "
    "9820466726, iCall at 9152987821, or the KIRAN helpline at 1800-599-0019, any "
    "time of day or night. If you're in immediate danger, please call 112. "
    "Would you like to tell me a bit more about what's been going on?"
)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_settings():
    settings = load_json(SETTINGS_FILE, None)
    if settings is None:
        settings = DEFAULT_SETTINGS.copy()
        save_json(SETTINGS_FILE, settings)
    return settings


def get_conversations():
    return load_json(CONV_FILE, {})


def save_conversation(session_id, role, text):
    conversations = get_conversations()
    conv = conversations.get(session_id)
    if conv is None:
        conv = {
            "session_id": session_id,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "messages": [],
        }
        conversations[session_id] = conv
    conv["messages"].append(
        {"role": role, "text": text, "timestamp": datetime.utcnow().isoformat() + "Z"}
    )
    conv["last_updated"] = datetime.utcnow().isoformat() + "Z"
    save_json(CONV_FILE, conversations)


def contains_crisis_language(text):
    lowered = text.lower()
    return any(kw in lowered for kw in CRISIS_KEYWORDS)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def escape_xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---------------- User-facing chat ----------------

@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    settings = get_settings()
    return render_template("index.html", bot_name=settings["bot_name"])


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return jsonify({"error": "Empty message"}), 400

    session_id = session.get("session_id") or str(uuid.uuid4())
    session["session_id"] = session_id

    save_conversation(session_id, "user", user_text)

    settings = get_settings()

    if contains_crisis_language(user_text):
        reply_text = CRISIS_MESSAGE
    elif client is None:
        reply_text = (
            "I'd love to talk with you, but my connection to the AI service isn't "
            "set up yet. Please add an Anthropic API key on the server."
        )
    else:
        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system=settings["system_prompt"],
                messages=[{"role": "user", "content": user_text}],
            )
            reply_text = "".join(
                block.text for block in resp.content if getattr(block, "type", "") == "text"
            ).strip() or "I'm here with you. Can you tell me a little more?"
        except Exception:
            reply_text = (
                "I'm having a little trouble reaching my thinking service right now, "
                "but I'm still here. Can you tell me more about how you're feeling?"
            )

    save_conversation(session_id, "bot", reply_text)
    return jsonify({"reply": reply_text})


@app.route("/api/speak", methods=["POST"])
def speak():
    """Convert text to speech using Azure Speech and return base64 audio."""
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Empty text"}), 400

    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        return jsonify({"error": "Azure speech not configured"}), 503

    settings = get_settings()
    voice_name = settings.get("voice_name", "en-IN-NeerjaNeural")

    ssml = (
        "<speak version='1.0' xml:lang='en-US'>"
        f"<voice xml:lang='en-US' xml:gender='Female' name='{voice_name}'>"
        f"{escape_xml(text)}"
        "</voice></speak>"
    )

    url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-64kbitrate-mono-mp3",
        "User-Agent": "emotion-companion-bot",
    }

    try:
        r = requests.post(url, headers=headers, data=ssml.encode("utf-8"), timeout=15)
        r.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"Azure TTS failed: {exc}"}), 502

    audio_b64 = base64.b64encode(r.content).decode("ascii")
    return jsonify({"audio_base64": audio_b64, "mime": "audio/mpeg"})


# ---------------- Admin ----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid username or password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conversations = get_conversations()
    conv_list = sorted(
        conversations.values(), key=lambda c: c.get("last_updated", ""), reverse=True
    )
    return render_template("admin_dashboard.html", conversations=conv_list)


@app.route("/admin/conversation/<session_id>")
@admin_required
def admin_conversation(session_id):
    conversations = get_conversations()
    conv = conversations.get(session_id)
    if not conv:
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_conversation.html", conv=conv)


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    settings = get_settings()
    saved = False
    if request.method == "POST":
        settings["bot_name"] = request.form.get("bot_name", settings["bot_name"])
        settings["system_prompt"] = request.form.get("system_prompt", settings["system_prompt"])
        settings["voice_name"] = request.form.get("voice_name", settings["voice_name"])
        save_json(SETTINGS_FILE, settings)
        saved = True
    return render_template("admin_settings.html", settings=settings, saved=saved)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
