"""Tests must be OFFLINE and independent of your .env: force mock LLM + BM25 retrieval BEFORE anything imports `lawyer`."""
import os, sys
from pathlib import Path
os.environ["LLM_PROVIDER"] = "mock"
os.environ["RETRIEVAL_BACKEND"] = "bm25"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
