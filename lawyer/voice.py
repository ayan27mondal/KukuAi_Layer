"""Voice: free speech-to-text (Groq Whisper, Gemini fallback) and free text-to-speech (gTTS, no key)."""
import base64, io, re
import requests
from . import config, llm

class VoiceError(Exception):
    pass

MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4", "ogg": "audio/ogg", "webm": "audio/webm", "flac": "audio/flac"}

def transcribe(audio_bytes, filename="audio.wav", language=None):
    """Return the transcript. `language` = ISO code like 'hi', 'bn', 'as', 'en' (None = auto-detect)."""
    errors = []
    if config.GROQ_API_KEY():
        try:
            data = {"model": config.GROQ_STT_MODEL(), "response_format": "json", "temperature": "0"}
            if language:
                data["language"] = language
            r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                              headers={"Authorization": f"Bearer {config.GROQ_API_KEY()}"},
                              files={"file": (filename, audio_bytes)}, data=data, timeout=120)
            if r.status_code < 400:
                return r.json()["text"].strip()
            errors.append(f"groq {r.status_code}: {r.text[:150]}")
        except requests.RequestException as e:
            errors.append(f"groq: {llm.redact(e)}")
    if config.GEMINI_API_KEY():
        try:
            ext = filename.rsplit(".", 1)[-1].lower()
            payload = {"contents": [{"parts": [
                {"text": "Transcribe this audio exactly, in the original language and script. Output only the transcript."},
                {"inline_data": {"mime_type": MIME.get(ext, "audio/wav"), "data": base64.b64encode(audio_bytes).decode()}}]}]}
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL()}:generateContent"
            r = requests.post(url, json=payload, headers={"x-goog-api-key": config.GEMINI_API_KEY()}, timeout=120)
            if r.status_code < 400:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            errors.append(f"gemini {r.status_code}: {r.text[:150]}")
        except (requests.RequestException, KeyError, IndexError) as e:
            errors.append(f"gemini: {llm.redact(e)}")
    raise VoiceError("Speech-to-text failed. " + (" | ".join(errors) if errors else "Add GROQ_API_KEY or GEMINI_API_KEY to .env."))

TTS_LANG = {"en": ("en", "co.in"), "hinglish": ("en", "co.in"), "hi": ("hi", "com"), "bn": ("bn", "com")}   # Assamese is not supported by gTTS

def clean_for_speech(text):
    t = re.sub(r"\[[A-Z0-9][A-Z0-9\-_\.]{2,}\]", "", text)         # chunk ids
    t = re.sub(r"[*_`#>]|✅|❌|🗣️|⚠️|\[⚠[^\]]*\]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:1500]

def speak(text, lang="en"):
    """Return MP3 bytes, or None if the language is unsupported / offline."""
    if lang not in TTS_LANG:
        return None
    try:
        from gtts import gTTS
        code, tld = TTS_LANG[lang]
        buf = io.BytesIO()
        gTTS(clean_for_speech(text), lang=code, tld=tld).write_to_fp(buf)
        return buf.getvalue()
    except Exception:
        return None
