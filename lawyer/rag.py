"""Retrieval layer.

* Chunk / parse_corpus: reads corpus/*.md (format below).
* Index: offline BM25 keyword search (always works, no API).
* get_index(): returns a HybridIndex = ChromaDB vector search (Gemini embeddings) with an automatic
  fallback to BM25 if Chroma cannot start (no key, no internet, quota) or fails on a query.

Corpus chunk format:
### CHUNK: <ID>
act: ... | section: ... | topic: ... | state: ... | source: ... | verified: ... | pointer_only: ... | quarantine: true
text: ... (until the next '### CHUNK:')
A chunk with `quarantine: true` is NEVER loaded - use it for notes you found to be wrong/outdated.
"""
import math, re
from collections import Counter
from dataclasses import dataclass, field
from . import config

STOP = set("a an the of to in on for and or is are was were be been it this that with as at by from my me i you your we they he she not no do does did can could should would will have has had if then than so but about what how when where which who whom into out up down over under after before again any all some".split())

@dataclass
class Chunk:
    id: str
    text: str
    meta: dict = field(default_factory=dict)
    @property
    def act(self): return self.meta.get("act", "")
    @property
    def section(self): return self.meta.get("section", "")
    @property
    def topic(self): return self.meta.get("topic", "general")
    @property
    def verified(self): return self.meta.get("verified", "false").lower() == "true"

def tokenize(s):
    return [t for t in re.findall(r"\w+", s.lower()) if t not in STOP and len(t) > 1]

def parse_corpus(directory=None, include_quarantined=False):
    chunks, seen = [], set()
    for path in sorted((directory or config.CORPUS_DIR).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        for block in raw.split("### CHUNK:")[1:]:
            lines = block.strip().splitlines()
            cid = lines[0].strip()
            meta, text_lines, in_text = {}, [], False
            for ln in lines[1:]:
                if in_text:
                    text_lines.append(ln)
                elif ln.startswith("text:"):
                    in_text = True
                    rest = ln[5:].strip()
                    if rest:
                        text_lines.append(rest)
                elif ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip()
            meta["file"] = path.name
            if meta.get("quarantine", "false").lower() == "true" and not include_quarantined:
                continue
            if cid in seen:
                raise ValueError(f"Duplicate chunk id in corpus: {cid}")
            seen.add(cid)
            chunks.append(Chunk(cid, "\n".join(text_lines).strip(), meta))
    return chunks

def _topics(topic):
    """topic filter -> set of allowed topics (never the internal 'meta' notes)."""
    if topic is None:
        return None
    base = {topic} if isinstance(topic, str) else set(topic)
    return base | {"general"}

class Index:
    """BM25 keyword index."""
    backend = "bm25"
    def __init__(self, chunks=None, k1=1.5, b=0.75):
        self.chunks = chunks if chunks is not None else parse_corpus()
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(c.text + " " + c.act + " " + c.meta.get("title", ""))) for c in self.chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 1
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def by_id(self, cid):
        return next((c for c in self.chunks if c.id == cid), None)

    def states_with_full_coverage(self):
        return {c.meta["state"].lower() for c in self.chunks
                if c.meta.get("state") and c.meta.get("pointer_only", "false").lower() != "true"}

    def states_with_pointer(self):
        return {c.meta["state"].lower() for c in self.chunks if c.meta.get("state")}

    def min_score(self):
        return config.MIN_RETRIEVAL_SCORE()

    def search(self, query, k=5, topic=None):
        """[(Chunk, score)] best first."""
        q = tokenize(query)
        allowed = _topics(topic)
        out = []
        for i, c in enumerate(self.chunks):
            if c.topic == "meta" or (allowed and c.topic not in allowed):
                continue
            d, L, s = self.docs[i], self.lens[i], 0.0
            for t in q:
                f = d.get(t, 0)
                if f:
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * L / self.avg))
            if s > 0:
                out.append((c, s))
        out.sort(key=lambda x: -x[1])
        return out[:k]

class HybridIndex:
    """Chroma first, BM25 as a safety net. Same interface as Index plus `backend`, `last_error`, `min_score()`."""
    def __init__(self, primary, fallback, init_error=None):
        self.primary, self.fallback = primary, fallback
        self.chunks = fallback.chunks
        self.last_error = init_error
        self.last_backend = "chroma" if primary is not None else "bm25"

    @property
    def backend(self):
        return self.last_backend

    @property
    def backend_label(self):
        base = "ChromaDB (vector)" if self.last_backend == "chroma" else "BM25 (keyword)"
        return base + (" - fallback: " + self.last_error[:80] if self.last_backend == "bm25" and self.last_error else "")

    def by_id(self, cid): return self.fallback.by_id(cid)
    def states_with_full_coverage(self): return self.fallback.states_with_full_coverage()
    def states_with_pointer(self): return self.fallback.states_with_pointer()

    def min_score(self):
        return self.primary.min_score() if self.last_backend == "chroma" else self.fallback.min_score()

    def search(self, query, k=5, topic=None):
        if self.primary is not None:
            try:
                hits = self.primary.search(query, k=k, topic=topic)
                self.last_backend = "chroma"
                return hits
            except Exception as e:                       # network / quota / API errors
                from .llm import redact
                self.last_error = redact(e)
                print(f"[rag] Chroma search failed, using BM25: {self.last_error[:150]}")
        self.last_backend = "bm25"
        return self.fallback.search(query, k=k, topic=topic)

_INDEX = None

def get_index(reload=False):
    global _INDEX
    if _INDEX is not None and not reload:
        return _INDEX
    chunks = parse_corpus()
    bm25 = Index(chunks)
    primary, err = None, None
    if config.retrieval_backend() == "chroma":
        try:
            from .rag_chroma import ChromaIndex
            primary = ChromaIndex(chunks)
        except Exception as e:
            from .llm import redact
            err = redact(e)
            print(f"[rag] ChromaDB unavailable ({err[:150]}). Falling back to BM25 keyword search.")
    _INDEX = HybridIndex(primary, bm25, err)
    return _INDEX
