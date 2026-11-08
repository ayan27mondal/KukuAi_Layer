"""ChromaDB vector index with Gemini embeddings (free tier).

Fixes vs the first version:
* cosine distance is configured explicitly (hnsw:space=cosine), score = 1 - distance
* documents and queries use the correct Gemini task types (RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY)
* ALL embeddings are computed first, then written; the stored fingerprint therefore always means "complete"
* the index rebuilds automatically when the corpus, embedding model or distance setting changes
* batched embedding calls + retry on rate limits (free tier) instead of one HTTP call per chunk
* the API key is sent in a header, never in the URL
"""
import hashlib, math, time
from pathlib import Path
import requests
from . import config, llm
from .rag import Chunk, parse_corpus, _topics   # noqa: F401  (Chunk re-exported for old imports)

BASE = llm.GEMINI_BASE
SPACE = "cosine"

def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

class GeminiEmbeddings:
    def __init__(self, api_key, model="gemini-embedding-001"):
        self.api_key, self.model = api_key, model

    def _model_path(self):
        return self.model if self.model.startswith("models/") else f"models/{self.model}"

    def _post(self, url, payload, retries=4):
        last = None
        for i in range(retries):
            r = requests.post(url, json=payload, headers={"x-goog-api-key": self.api_key}, timeout=60)
            if r.status_code in (429, 500, 502, 503):
                last = f"HTTP {r.status_code}"
                time.sleep(2 * (i + 1))
                continue
            if r.status_code == 404 and not getattr(self, "_retried_model", False):
                self._retried_model = True                      # embedding model retired -> pick a current one
                names = llm.gemini_models("embedContent")
                new = llm.pick_model(names, "embedding")
                if new:
                    print(f"[rag] embedding model '{self.model}' not found; using '{new}'")
                    self.model = new
                    payload = self._rewrite_model(payload)
                    url = url.rsplit("/models/", 1)[0] + f"/models/{new}:" + url.rsplit(":", 1)[1]
                    continue
            if r.status_code >= 400:
                raise RuntimeError(llm.redact(f"Gemini embedding error: HTTP {r.status_code} {r.text[:200]}"))
            return r.json()
        raise RuntimeError(f"Gemini embedding rate-limited or unavailable ({last})")

    def _rewrite_model(self, payload):
        if "requests" in payload:
            for q in payload["requests"]:
                q["model"] = self._model_path()
        return payload

    def _embed(self, texts, task):
        payload = {"requests": [{"model": self._model_path(), "content": {"parts": [{"text": t or "legal query"}]}, "taskType": task} for t in texts]}
        d = self._post(f"{BASE}/{self._model_path()}:batchEmbedContents", payload)
        return [_unit(e["values"]) for e in d["embeddings"]]

    def embed_documents(self, texts, batch=50):
        out = []
        for i in range(0, len(texts), batch):
            out += self._embed(texts[i:i + batch], "RETRIEVAL_DOCUMENT")
        return out

    def embed_query(self, text):
        return self._embed([text if text and text.strip() else "legal query"], "RETRIEVAL_QUERY")[0]

def _fingerprint(chunks, model):
    h = hashlib.sha256((model + "|" + SPACE).encode())
    for c in chunks:
        h.update((c.id + "\x00" + c.text + "\x00" + c.act + "\x00" + c.topic).encode())
    return h.hexdigest()[:20]

class ChromaIndex:
    backend = "chroma"
    def __init__(self, chunks=None, persist_dir=None, collection_name=None, embedder=None):
        self.chunks = chunks if chunks is not None else parse_corpus()
        self.persist_dir = Path(persist_dir or config.CHROMA_PERSIST_DIR)
        self.collection_name = collection_name or config.CHROMA_COLLECTION
        if embedder is None:
            if not config.GEMINI_API_KEY():
                raise RuntimeError("GEMINI_API_KEY is required for the Chroma backend (or set RETRIEVAL_BACKEND=bm25)")
            embedder = GeminiEmbeddings(config.GEMINI_API_KEY(), config.GEMINI_EMBEDDING_MODEL())
        self.embeddings = embedder
        import chromadb
        from chromadb.config import Settings
        self.client = chromadb.PersistentClient(path=str(self.persist_dir), settings=Settings(anonymized_telemetry=False))
        self._ensure_collection()

    def _model_name(self):
        return getattr(self.embeddings, "model", "custom")

    def _ensure_collection(self):
        fp = _fingerprint(self.chunks, self._model_name())
        col = None
        try:
            col = self.client.get_collection(self.collection_name)
        except Exception:
            col = None                                           # does not exist yet
        if col is not None:
            ok = (col.metadata or {}).get("corpus_fingerprint") == fp and col.count() == len(self.chunks)
            if ok:
                self.collection = col
                return
            print("[rag] corpus / embedding settings changed or index incomplete - rebuilding ChromaDB index")
            self.client.delete_collection(self.collection_name)
        self._build(fp)

    def _build(self, fp):
        docs = [c.text + " " + c.act for c in self.chunks]
        vectors = self.embeddings.embed_documents(docs)          # may raise -> nothing is written (no half-built index)
        col = self.client.create_collection(name=self.collection_name, metadata={"corpus_fingerprint": fp, "hnsw:space": SPACE})
        metas = [{"act": c.act, "section": c.section, "topic": c.topic, "state": c.meta.get("state", ""),
                  "verified": c.verified, "file": c.meta.get("file", "")} for c in self.chunks]
        for i in range(0, len(docs), 100):
            col.add(ids=[c.id for c in self.chunks[i:i + 100]], documents=docs[i:i + 100],
                    embeddings=vectors[i:i + 100], metadatas=metas[i:i + 100])
        self.collection = col
        print(f"[rag] ChromaDB index built: {col.count()} chunks")

    def by_id(self, cid):
        return next((c for c in self.chunks if c.id == cid), None)

    def states_with_full_coverage(self):
        return {c.meta["state"].lower() for c in self.chunks if c.meta.get("state") and c.meta.get("pointer_only", "false").lower() != "true"}

    def states_with_pointer(self):
        return {c.meta["state"].lower() for c in self.chunks if c.meta.get("state")}

    def min_score(self):
        return config.MIN_CHROMA_SIMILARITY()

    def search(self, query, k=5, topic=None):
        """[(Chunk, cosine similarity 0..1)] best first. 'meta' notes are never returned."""
        allowed = _topics(topic)
        where = {"topic": {"$in": sorted(allowed)}} if allowed else {"topic": {"$ne": "meta"}}
        res = self.collection.query(query_embeddings=[self.embeddings.embed_query(query)], n_results=max(1, min(k, self.collection.count())),
                                    where=where, include=["distances"])
        out = []
        for cid, dist in zip(res["ids"][0], res["distances"][0]):
            c = self.by_id(cid)
            if c:
                out.append((c, 1.0 - float(dist)))
        out.sort(key=lambda x: -x[1])
        return out

def get_chroma_index(reload=False):
    from . import rag
    return rag.get_index(reload)
