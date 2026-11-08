import pytest
from lawyer import config, llm, rag

def test_api_keys_are_redacted_from_errors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-KEY-123")
    assert "SECRET-KEY-123" not in llm.redact("failed https://x/y?key=SECRET-KEY-123&a=1 SECRET-KEY-123")
    assert "key=***" in llm.redact("https://x?key=abcdef")

def test_parse_json_handles_code_fences():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('blah {"a": 2} blah') == {"a": 2}

def test_pick_model_prefers_current_flash_and_avoids_lite_preview():
    names = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-3-flash"]
    assert llm.pick_model(names, "flash") == "gemini-3-flash"
    assert llm.pick_model(["text-embedding-004", "gemini-embedding-001"], "embedding") == "text-embedding-004"

def test_corpus_ids_are_unique_and_every_chunk_has_text_and_topic():
    chunks = rag.parse_corpus()
    assert len({c.id for c in chunks}) == len(chunks) and all(c.text and c.topic for c in chunks)

def test_quarantined_chunks_are_never_loaded():
    ids = {c.id for c in rag.parse_corpus()}
    assert "HMA-SECTION-13-1A" not in ids
    assert "HMA-SECTION-13-1A-WIFE-GROUNDS" in {c.id for c in rag.parse_corpus(include_quarantined=True)}

def test_old_consumer_limits_cannot_be_retrieved():
    hits = rag.Index().search("district commission pecuniary jurisdiction crore", k=10, topic="consumer")
    assert all("up to Rs 1 crore" not in c.text for c, _ in hits)

def test_meta_notes_are_never_retrieved():
    assert all(c.topic != "meta" for c, _ in rag.Index().search("what this tool covers", k=30))
