import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def providers():
    raw = os.getenv("LLM_PROVIDER", "mock")
    return [p.strip().lower() for p in raw.split(",") if p.strip()]

def is_mock():
    return providers() == ["mock"]

# Retrieval backend: "bm25" (default, offline) or "chroma" (vector DB)
def retrieval_backend():
    return os.getenv("RETRIEVAL_BACKEND", "bm25").strip().lower()

# ChromaDB settings
def _persist_dir():
    raw = os.getenv("CHROMA_PERSIST_DIR", "").strip()
    if not raw:
        return ROOT / "chroma_db"
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p).resolve()
CHROMA_PERSIST_DIR = _persist_dir()
CHROMA_COLLECTION = "legal_corpus"

GROQ_API_KEY = lambda: os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = lambda: os.getenv("GEMINI_API_KEY", "").strip()
GROQ_MODEL = lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_STT_MODEL = lambda: os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
GEMINI_MODEL = lambda: os.getenv("GEMINI_MODEL", "gemini-flash-latest")
# Embedding model for ChromaDB (Gemini)
GEMINI_EMBEDDING_MODEL = lambda: os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
LARGE_AMOUNT_THRESHOLD = lambda: int(os.getenv("LARGE_AMOUNT_THRESHOLD", "500000"))
MIN_RETRIEVAL_SCORE = lambda: float(os.getenv("MIN_RETRIEVAL_SCORE", "2.0"))
# ChromaDB similarity threshold (cosine similarity 0-1, higher = better)
MIN_CHROMA_SIMILARITY = lambda: float(os.getenv("MIN_CHROMA_SIMILARITY", "0.5"))

CORPUS_DIR = ROOT / "corpus"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "generated"
FONT_DIR = ROOT / "assets" / "fonts"

DISCLAIMER = {
    "en": "This is legal information, not legal advice. For your specific case please consult a lawyer or free legal aid (DLSA / NALSA helpline 15100).",
    "hi": "यह कानूनी जानकारी है, कानूनी सलाह नहीं। अपने मामले के लिए कृपया वकील या मुफ़्त कानूनी सहायता (DLSA / NALSA हेल्पलाइन 15100) से संपर्क करें।",
    "hinglish": "Yeh legal information hai, legal advice nahi. Apne case ke liye please kisi vakeel ya free legal aid (DLSA / NALSA helpline 15100) se baat karein.",
}
LANG_NAMES = {"en": "English", "hi": "Hindi (Devanagari script)", "hinglish": "Hinglish (Hindi written in English letters)",
              "bn": "Bengali", "as": "Assamese"}
