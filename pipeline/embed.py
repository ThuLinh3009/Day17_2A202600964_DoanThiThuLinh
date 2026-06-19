"""Bonus: unstructured -> chunk -> embedding ingestion (zero-key).

Mirrors the deck's RAG-ingestion pipeline. We use a deterministic hash-based
'embedder' so the lab runs with no API key and no model download — the point is
the *pipeline shape* (parse -> recursive chunk -> embed -> store), not embedding
quality. Swap `embed_text` for a real model in the extension exercise.
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path

EMBED_DIM = 16


def recursive_chunks(text: str, size: int = 120, overlap: int = 20) -> list[str]:
    """Recursive-ish splitter on paragraph/sentence boundaries with overlap.
    Recursive ~fixed-size splitting is the strong 2026 default (deck §3)."""
    words = re.split(r"\s+", text.strip())
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + size]))
        i += size - overlap
    return [c for c in chunks if c]


def embed_text(text: str) -> list[float]:
    """Deterministic fake embedding: stable, no key. NOT semantically meaningful."""
    vec = [0.0] * EMBED_DIM
    for tok in re.findall(r"[a-zA-Z]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % EMBED_DIM] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [round(v / norm, 4) for v in vec]


def ingest_docs(docs_dir: Path) -> list[dict]:
    """parse -> chunk -> embed for every doc; returns rows ready for a vector store."""
    rows = []
    for path in sorted(Path(docs_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for idx, chunk in enumerate(recursive_chunks(text)):
            rows.append(
                {
                    "doc": path.name,
                    "chunk_id": idx,
                    "text": chunk,
                    "embedding": embed_text(chunk),
                }
            )
    return rows
