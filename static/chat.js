const chatWindow = document.getElementById("chatWindow");
const textInput = document.getElementById("textInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");

function addBubble(text, who) {
  const el = document.createElement("div");
  el.className = `bubble ${who}`;
  el.textContent = text;
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return el;
}

async function playReply(text) {
  try {
    const res = await fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return; // voice not configured — text reply is already shown
    const data = await res.json();
    const audio = new Audio(`data:${data.mime};base64,${data.audio_base64}`);
    audio.play();
  } catch (e) {
    // silently ignore — text reply still stands
  }
}

async function sendMessage(text) {
  if (!text.trim()) return;
  addBubble(text, "user");
  textInput.value = "";

  const typingEl = addBubble("...", "bot typing");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    typingEl.remove();
    if (data.reply) {
      addBubble(data.reply, "bot");
      playReply(data.reply);
    } else {
      addBubble("Sorry, something went wrong on my end.", "bot");
    }
  } catch (e) {
    typingEl.remove();
    addBubble("I couldn't reach the server just now. Please try again.", "bot");
  }
}

sendBtn.addEventListener("click", () => sendMessage(textInput.value));
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage(textInput.value);
});

// --- Voice input via the browser's built-in speech recognition ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizing = false;
let recognizer = null;

if (SpeechRecognition) {
  recognizer = new SpeechRecognition();
  recognizer.lang = "en-IN";
  recognizer.interimResults = false;
  recognizer.maxAlternatives = 1;

  recognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    sendMessage(transcript);
  };

  recognizer.onend = () => {
    recognizing = false;
    micBtn.classList.remove("listening");
  };

  recognizer.onerror = () => {
    recognizing = false;
    micBtn.classList.remove("listening");
  };

  micBtn.addEventListener("click", () => {
    if (recognizing) {
      recognizer.stop();
      return;
    }
    recognizing = true;
    micBtn.classList.add("listening");
    recognizer.start();
  });
} else {
  micBtn.title = "Voice input isn't supported in this browser";
  micBtn.addEventListener("click", () => {
    addBubble("Voice input isn't supported in this browser — try Chrome or Edge, or just type.", "bot");
  });
}

// Greet on load
window.addEventListener("DOMContentLoaded", () => {
  addBubble("Hi, I'm here to listen. How are you feeling today?", "bot");
});
