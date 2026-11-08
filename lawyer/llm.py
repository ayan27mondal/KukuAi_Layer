"""Thin wrappers over FREE LLM APIs (Groq, Gemini) using plain `requests`.
* Providers are tried in the order of LLM_PROVIDER; on failure the next one is used.
* API keys are sent in HEADERS (never in the URL) and are redacted from every error message.
* If a Gemini model name has been retired (HTTP 404) the code asks the API which models exist and picks a Flash model."""
import json, re, time
import requests
from . import config

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

class LLMError(Exception):
    pass

def redact(s):
    s = str(s)
    for k in (config.GROQ_API_KEY(), config.GEMINI_API_KEY()):
        if k:
            s = s.replace(k, "***")
    return re.sub(r"(key=)[^&\s'\"]+", r"\1***", s)

def _post(url, headers, payload, retries=3):
    last = None
    for i in range(retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(2 * (i + 1))
                continue
            if r.status_code >= 400:
                raise LLMError(redact(f"HTTP {r.status_code}: {r.text[:300]}"))
            return r.json()
        except requests.RequestException as e:
            last = redact(e)
            time.sleep(2 * (i + 1))
    raise LLMError(redact(last or "unknown error"))

def _groq(system, user, json_mode, temperature):
    key = config.GROQ_API_KEY()
    if not key:
        raise LLMError("GROQ_API_KEY missing")
    payload = {"model": config.GROQ_MODEL(), "temperature": temperature,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    d = _post("https://api.groq.com/openai/v1/chat/completions", {"Authorization": f"Bearer {key}"}, payload)
    return d["choices"][0]["message"]["content"]

_RESOLVED = {}

def gemini_models(method):
    """Names of models that currently support `method` (e.g. generateContent, embedContent)."""
    key = config.GEMINI_API_KEY()
    r = requests.get(f"{GEMINI_BASE}/models?pageSize=200", headers={"x-goog-api-key": key}, timeout=30)
    if r.status_code >= 400:
        raise LLMError(redact(f"listing models failed: HTTP {r.status_code}"))
    return [m["name"].split("/", 1)[1] for m in r.json().get("models", []) if method in m.get("supportedGenerationMethods", [])]

def pick_model(names, want):
    """Prefer `want` words (e.g. 'flash'); avoid lite/preview/experimental/image/audio variants; newest-looking name first."""
    bad = ("lite", "preview", "exp", "image", "tts", "audio", "live", "thinking", "robotics", "computer", "vision")
    good = [n for n in names if want in n and not any(b in n for b in bad)]
    return sorted(good, reverse=True)[0] if good else (names[0] if names else None)

def _gemini_call(model, system, user, json_mode, temperature):
    gen = {"temperature": temperature}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    payload = {"system_instruction": {"parts": [{"text": system}]},
               "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": gen}
    d = _post(f"{GEMINI_BASE}/models/{model}:generateContent", {"x-goog-api-key": config.GEMINI_API_KEY()}, payload)
    return d["candidates"][0]["content"]["parts"][0]["text"]

def _gemini(system, user, json_mode, temperature):
    if not config.GEMINI_API_KEY():
        raise LLMError("GEMINI_API_KEY missing")
    model = _RESOLVED.get("gen") or config.GEMINI_MODEL()
    try:
        return _gemini_call(model, system, user, json_mode, temperature)
    except LLMError as e:
        if "HTTP 404" not in str(e):
            raise
        new = pick_model(gemini_models("generateContent"), "flash")      # the configured model was retired
        if not new:
            raise LLMError(f"Gemini model '{model}' not found and no replacement available") from e
        _RESOLVED["gen"] = new
        print(f"[llm] Gemini model '{model}' not found; using '{new}'. Set GEMINI_MODEL={new} in .env to silence this.")
        return _gemini_call(new, system, user, json_mode, temperature)

def chat(system, user, json_mode=False, temperature=0.2):
    errors = []
    for p in config.providers():
        try:
            if p == "groq":
                return _groq(system, user, json_mode, temperature)
            if p == "gemini":
                return _gemini(system, user, json_mode, temperature)
            errors.append(f"{p}: unknown provider")
        except (LLMError, KeyError, IndexError) as e:
            errors.append(f"{p}: {redact(e)}")
    raise LLMError(" | ".join(errors))

def parse_json(text):
    """Robustly pull a JSON object out of an LLM reply."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            return json.loads(text[s:e + 1])
        raise
