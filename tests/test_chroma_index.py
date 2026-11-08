"""ChromaDB plumbing tested OFFLINE with a fake embedder (no Gemini calls)."""
import math, re
import pytest
from lawyer import rag
from lawyer.rag_chroma import ChromaIndex

class FakeEmbedder:
    model = "fake-v1"
    def __init__(self, fail=False): self.fail, self.calls = fail, 0
    def _v(self, t):
        v = [0.0] * 256
        for w in re.findall(r"\w+", t.lower()):
            v[hash(w) % 256] += 1
        n = math.sqrt(sum(x * x for x in v)) or 1
        return [x / n for x in v]
    def embed_documents(self, texts):
        self.calls += 1
        if self.fail: raise RuntimeError("quota exceeded")
        return [self._v(t) for t in texts]
    def embed_query(self, t): return self._v(t)

CH = rag.parse_corpus()

def test_builds_searches_and_scores_with_cosine(tmp_path):
    ix = ChromaIndex(CH, persist_dir=tmp_path, embedder=FakeEmbedder())
    chunk = ix.by_id("MTA2021-S11-DEPOSIT-CAP")
    hits = ix.search(chunk.text + " " + chunk.act, k=3)
    assert hits[0][0].id == "MTA2021-S11-DEPOSIT-CAP" and hits[0][1] > 0.99          # identical text -> cosine ~ 1
    assert all(0 <= s <= 1.0001 for _, s in hits)

def test_topic_filter_and_meta_notes_hidden(tmp_path):
    ix = ChromaIndex(CH, persist_dir=tmp_path, embedder=FakeEmbedder())
    assert all(c.topic in ("salary", "general") for c, _ in ix.search("unpaid salary employer", k=8, topic="salary"))
    assert all(c.topic != "meta" for c, _ in ix.search("what this tool covers", k=20))

def test_reuses_persisted_index_without_re_embedding(tmp_path):
    ChromaIndex(CH, persist_dir=tmp_path, embedder=FakeEmbedder())
    e2 = FakeEmbedder(); ChromaIndex(CH, persist_dir=tmp_path, embedder=e2)
    assert e2.calls == 0

def test_rebuilds_when_corpus_changes(tmp_path):
    ChromaIndex(CH, persist_dir=tmp_path, embedder=FakeEmbedder())
    changed = list(CH); changed[0] = rag.Chunk(CH[0].id, CH[0].text + " NEW TEXT", CH[0].meta)
    e2 = FakeEmbedder(); ChromaIndex(changed, persist_dir=tmp_path, embedder=e2)
    assert e2.calls == 1

def test_failed_build_leaves_no_half_built_index(tmp_path):
    with pytest.raises(RuntimeError): ChromaIndex(CH, persist_dir=tmp_path, embedder=FakeEmbedder(fail=True))
    e = FakeEmbedder(); ix = ChromaIndex(CH, persist_dir=tmp_path, embedder=e)     # next start recovers fully
    assert e.calls == 1 and ix.collection.count() == len(CH)

def test_hybrid_falls_back_to_bm25_when_chroma_search_fails(tmp_path):
    class Broken:
        def search(self, *a, **k): raise RuntimeError("HTTP 429 quota")
        def min_score(self): return 0.5
    h = rag.HybridIndex(Broken(), rag.Index(CH))
    hits = h.search("landlord deposit refund", k=3, topic="deposit")
    assert hits and h.backend == "bm25" and "429" in h.last_error and h.min_score() == rag.Index(CH).min_score()
