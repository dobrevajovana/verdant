"""Embedding similarity: names and candidate terms embedded with SentenceTransformers and
compared by cosine similarity (as in VERDANT's vector-matching step).

Optional: ``pip install "verdy[embeddings]"``. Without it VERDY matches on words alone.
"""

from __future__ import annotations

import os

MODEL = os.environ.get("VERDY_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
MIN_COSINE = 0.70     # least cosine for a match kept on embedding similarity (match(min_cosine=...))
CLOSE = 0.80          # cosine for a closeMatch

_models: dict = {}


def available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def encode(texts: list[str], model: str = MODEL):
    """Unit-length vectors, so a dot product is the cosine similarity."""
    if model not in _models:
        os.environ.setdefault("OMP_NUM_THREADS", "1")      # PyTorch's OpenMP: one thread avoids clashes
        from sentence_transformers import SentenceTransformer
        _models[model] = SentenceTransformer(model)
    return _models[model].encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)


def candidate_text(hit: dict) -> str:
    """A candidate as text: its label, up to five synonyms and the start of its definition."""
    parts = [hit.get("label") or ""]
    if hit.get("synonyms"):
        parts.append("also called " + ", ".join(hit["synonyms"][:5]))
    if hit.get("definition"):
        parts.append(str(hit["definition"])[:300])
    return ". ".join(p for p in parts if p)


def cosine(left: list[str], right: list[str], model: str = MODEL) -> list[float]:
    """Cosine similarity of each pair (left[i], right[i])."""
    if not left:
        return []
    texts = list(dict.fromkeys(left + right))
    vectors = dict(zip(texts, encode(texts, model)))
    return [float(vectors[a] @ vectors[b]) for a, b in zip(left, right)]
