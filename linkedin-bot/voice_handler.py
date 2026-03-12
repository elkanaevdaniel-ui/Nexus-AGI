"""voice_handler.py - JARVIS v0.1 Voice System for NEXUS AGI

COMMAND Division - NEXUS AGI
Features: JARVIS personality, British TTS, persistent memory, intent routing.
"""
import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import speech_recognition as sr
except ImportError:
    sr = None  # voice STT unavailable — bot still works for text

try:
    from gtts import gTTS
except ImportError:
    gTTS = None  # voice TTS unavailable — bot still works for text

from google import genai
from google.genai import types as genai_types

from config import GOOGLE_API_KEY

log = logging.getLogger(__name__)

# == Paths =================================================================
_DIR         = Path(__file__).resolve().parent
_DATA_DIR    = _DIR / "data"
_MEMORY_FILE = _DATA_DIR / "jarvis_memory.json"
_NEXUS_DIR   = _DIR.parent / "nexus-agi"
_MASTER_PLAN = _NEXUS_DIR / "docs" / "NEXUS_MASTER_PLAN.md"
_TASKS_FILE  = _NEXUS_DIR / "docs" / "NEXUS_TASKS.md"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_HISTORY          = 20
MAX_MEMORY_TURNS     = 50
MEMORY_CONTEXT_TURNS = 8

_gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
_CONVERSATION_HISTORY: dict[int, list[dict]] = {}

# == JARVIS Personality Prompt =============================================
_P = (
    "You are JARVIS (Just A Rather Very Intelligent System), "
    "the AI assistant for NEXUS AGI - building autonomous software on demand.\n\n"
    "Personality:\n"
    "- Formal, intelligent, loyal, occasionally witty - Iron Man AI style\n"
    "- Address user as sir occasionally (every 3-4 replies)\n"
    "- British spelling: colour, honour, analyse, whilst\n"
    "- Voice replies: max 4 sentences, no markdown, speak naturally\n"
    "- Dry wit when appropriate\n\n"
    "NEXUS Divisions:\n"
    "- HERALD: LinkedIn social media (fully operational)\n"
    "- SIGMA: crypto trading bot 30pct ROI target (planning)\n"
    "- COMMAND: JARVIS + user interface (your division)\n"
    "- FORGE: software development\n\n"
    "Bot Commands (include exact token when requested):\n"
    "POST_NOW SHOW_LAST SHOW_SCHEDULE SHOW_HELP\n\n"
    "Date: {date}\n"
    "Recent context:\n{memory_context}"
)
JARVIS_SYSTEM_PROMPT = _P
SYSTEM_PROMPT = _P  # legacy

# == Persistent Memory =====================================================

def _load_persistent_memory() -> list[dict]:
    """Load JARVIS memory from JSON file."""
    if not _MEMORY_FILE.exists():
        return []
    try:
        with open(_MEMORY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.warning("JARVIS memory load error: %s", exc)
        return []


def _save_persistent_memory(memory: list[dict]) -> None:
    """Save JARVIS memory to JSON (last N turns)."""
    try:
        with open(_MEMORY_FILE, "w", encoding="utf-8") as fh:
            json.dump(memory[-MAX_MEMORY_TURNS:], fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        log.warning("JARVIS memory save error: %s", exc)


def _append_memory(user_text: str, jarvis_reply: str) -> None:
    """Append exchange to persistent memory."""
    mem = _load_persistent_memory()
    ts  = datetime.now().isoformat()
    mem.append({"role": "user",   "content": user_text,    "timestamp": ts})
    mem.append({"role": "jarvis", "content": jarvis_reply, "timestamp": ts})
    _save_persistent_memory(mem)


def _build_memory_context() -> str:
    """Return recent conversation context as plain text."""
    mem = _load_persistent_memory()
    if not mem:
        return "No previous conversations on record."
    parts = []
    for t in mem[-(MEMORY_CONTEXT_TURNS * 2):]:
        role    = "User" if t["role"] == "user" else "JARVIS"
        ts      = t.get("timestamp", "")[:16].replace("T", " ")
        content = t["content"][:120]
        parts.append("[" + ts + "] " + role + ": " + content)
    return "\n".join(parts)

# == Intent Detection ======================================================

_POST_KW   = ("post now", "make a post", "create post", "generate post",
              "post something", "create a post")
_NEXUS_KW  = ("nexus plan", "master plan", "show tasks", "nexus status",
              "the plan", "project status", "nexus report", "what are we building")
_STATUS_KW = ("how are you", "status report", "system status", "all systems",
              "how is everything", "operational", "are you online")
_HELP_KW   = ("what can you do", "your capabilities", "available commands",
              "show commands")


def _detect_intent(text: str) -> str:
    """Classify intent -> post | nexus | status | help | general."""
    t = text.lower().strip()
    if any(k in t for k in _POST_KW):   return "post"
    if any(k in t for k in _NEXUS_KW):  return "nexus"
    if any(k in t for k in _STATUS_KW): return "status"
    if "help" in t or any(k in t for k in _HELP_KW): return "help"
    return "general"

# == NEXUS Status Reader ===================================================

def _extract_section(text: str, keyword: str, max_lines: int = 20) -> str:
    """Extract a markdown section by header keyword."""
    in_sec = False
    out: list[str] = []
    for line in text.splitlines():
        if keyword.upper() in line.upper():
            in_sec = True
        elif in_sec and line.startswith("##") and keyword.upper() not in line.upper():
            break
        if in_sec:
            out.append(line)
        if len(out) >= max_lines:
            break
    return "\n".join(out)


def _read_nexus_summary() -> str:
    """Build NEXUS status summary from docs."""
    parts: list[str] = []
    for filepath, keyword, label, n in [
        (_TASKS_FILE,  "SPRINT 1",      "SPRINT 1 STATUS", 25),
        (_MASTER_PLAN, "PRIMARY GOALS", "PRIMARY GOALS",   10),
    ]:
        if filepath.exists():
            try:
                s = _extract_section(filepath.read_text(encoding="utf-8"), keyword, n)
                if s:
                    parts += ["=== " + label + " ===", s]
            except Exception as exc:
                log.warning("JARVIS docs read error: %s", exc)
    return "\n\n".join(parts) if parts else "NEXUS documentation unavailable."

# == Core AI - JARVIS Brain ================================================

async def get_jarvis_response(chat_id: int, user_text: str,
                               mode: str = "voice") -> str:
    """Get JARVIS personality response via Gemini.

    Args:
        chat_id:   Telegram chat ID.
        user_text: User input text.
        mode:      voice (<=3 sentences) or text (longer OK).
    """
    intent = _detect_intent(user_text)
    today  = datetime.now().strftime("%A, %d %B %Y")
    sysp   = JARVIS_SYSTEM_PROMPT.format(
        date=today, memory_context=_build_memory_context()
    )
    if mode == "voice":
        sysp += ("\n\nIMPORTANT: Spoken aloud via TTS. "
                 "Max 3 sentences. No markdown. Natural British English.")

    aug = user_text
    if intent == "nexus":
        aug = user_text + "\n\n[NEXUS DATA]:\n" + _read_nexus_summary()[:2000]
    elif intent == "status":
        aug = (user_text + "\n\n[JARVIS status: HERALD LinkedIn bot operational, "
               "7 image styles + FFmpeg video. JARVIS v0.1 active. "
               "SIGMA crypto bot planning. All nominal.]")
    elif intent == "post":
        aug = user_text + "\n\n[Confirm and include POST_NOW in response.]"

    history = _CONVERSATION_HISTORY.setdefault(chat_id, [])
    user_entry = {"role": "user", "parts": [{"text": aug}]}
    history.append(user_entry)
    if len(history) > MAX_HISTORY:
        _CONVERSATION_HISTORY[chat_id] = history[-MAX_HISTORY:]
        history = _CONVERSATION_HISTORY[chat_id]

    for _model in ["gemini-2.5-flash", "gemini-1.5-flash"]:
        try:
            resp = _gemini_client.models.generate_content(
                model=_model,
                contents=history,
                config=genai_types.GenerateContentConfig(
                    system_instruction=sysp,
                    temperature=0.78,
                    max_output_tokens=400 if mode == "voice" else 900,
                )
            )
            reply = resp.text
            if not reply:
                log.warning("JARVIS %s returned empty response", _model)
                continue
            reply = reply.strip()
            history.append({"role": "model", "parts": [{"text": reply}]})
            _append_memory(user_text, reply)
            log.info("JARVIS [%s %s] (%s): %s", chat_id, intent, _model, reply[:80])
            return reply
        except Exception as exc:
            log.warning("JARVIS Gemini %s error: %s", _model, exc)
            continue
    # All models failed — remove dangling user message to keep history valid
    if history and history[-1].get("role") == "user":
        history.pop()
    return ("My apologies, sir. I seem to be experiencing a momentary "
            "processing difficulty. Please try again shortly.")


async def get_nexus_status(chat_id: int) -> str:
    """Generate JARVIS-style NEXUS status report."""
    nd = _read_nexus_summary()
    return await get_jarvis_response(
        chat_id,
        "Concise JARVIS status report on NEXUS AGI. "
        "Sprint progress + top 2 priorities. 4 sentences max. British wit. "
        "Data:\n\n" + nd[:2000],
        mode="voice"
    )


async def get_ai_response(chat_id: int, user_text: str) -> str:
    """Legacy wrapper - routes through JARVIS."""
    return await get_jarvis_response(chat_id, user_text, mode="voice")

# == Audio Pipeline ========================================================

async def ogg_to_wav(ogg_path: str, wav_path: str) -> bool:
    """Convert Telegram OGG to WAV via FFmpeg."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=30
        )
        return r.returncode == 0
    except Exception as exc:
        log.error("OGG->WAV: %s", exc)
        return False


async def transcribe_audio(wav_path: str) -> str | None:
    """Transcribe WAV to text via Google STT."""
    if sr is None:
        log.warning("speech_recognition not installed — cannot transcribe")
        return None
    rec = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as src:
            audio = rec.record(src)
        text = rec.recognize_google(audio)
        log.info("JARVIS STT: %s", text)
        return text
    except sr.UnknownValueError:
        log.warning("JARVIS: speech not understood")
        return None
    except sr.RequestError as exc:
        log.error("STT error: %s", exc)
        return None


async def text_to_speech(text: str, output_path: str) -> bool:
    """Convert text to MP3 via gTTS - British accent (co.uk)."""
    if gTTS is None:
        log.warning("gTTS not installed — cannot generate speech")
        return False
    try:
        clean = re.sub(r"[*_`#]", "", text)
        clean = " ".join(clean.split())  # normalise whitespace
        tts = gTTS(text=clean, lang="en", tld="co.uk", slow=False)
        tts.save(output_path)
        log.info("JARVIS TTS (British): %s", output_path)
        return True
    except Exception as exc:
        log.error("TTS error: %s", exc)
        return False


async def mp3_to_ogg(mp3_path: str, ogg_path: str) -> bool:
    """Convert MP3 to OGG Opus (Telegram voice)."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-c:a", "libopus", ogg_path],
            capture_output=True, timeout=30
        )
        return r.returncode == 0
    except Exception as exc:
        log.error("MP3->OGG: %s", exc)
        return False

# == Utilities =============================================================

def detect_bot_command(text: str) -> str | None:
    """Return command token if present in AI response."""
    for cmd in ["POST_NOW", "SHOW_LAST", "SHOW_SCHEDULE", "SHOW_ANALYTICS", "SHOW_HELP"]:
        if cmd in text:
            return cmd
    return None


def clear_history(chat_id: int) -> None:
    """Clear in-session Gemini history for chat_id."""
    _CONVERSATION_HISTORY.pop(chat_id, None)
    log.info("JARVIS: session cleared chat=%s", chat_id)


def get_memory_stats() -> dict:
    """Return stats about JARVIS persistent memory."""
    mem = _load_persistent_memory()
    return {
        "total_turns": len(mem),
        "memory_file": str(_MEMORY_FILE),
        "oldest": mem[0].get("timestamp", "N/A")[:16] if mem else "N/A",
        "newest": mem[-1].get("timestamp", "N/A")[:16] if mem else "N/A",
    }
