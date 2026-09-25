"""Embeddings + semantic retrieval (pgvector) for the AI Scientist.

Embedding provider is pluggable:
  * ``openai``    — text-embedding-3-small (1536 dims) when OPENAI_API_KEY works.
  * ``mistral``   — mistral-embed when MISTRAL_API_KEY works.
  * ``hash``      — deterministic offline fallback (bag-of-character-ngrams
                    projected into 1536 dims). Not semantically deep, but
                    deterministic, dependency-free, and honest: identical text
                    ⇒ identical vector, related text ⇒ higher cosine than
                    unrelated text. Used when no provider is configured/working.

The schema's vector columns are ``vector(1536)`` to match all providers above.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional

EMBEDDING_DIM = 1536


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def _hash_embedding(text: str) -> List[float]:
    """Deterministic offline embedding: character 4-gram hashing → 1536 dims."""
    vec = [0.0] * EMBEDDING_DIM
    clean = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not clean:
        return vec
    grams = [clean[i:i + 4] for i in range(max(1, len(clean) - 3))]
    for gram in grams:
        digest = hashlib.md5(gram.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[index] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _openai_embedding(text: str) -> Optional[List[float]]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        request = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=__import__("json").dumps({
                "model": "text-embedding-3-small",
                "input": text[:8000],
            }).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"},
            method="POST")
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = __import__("json").loads(response.read().decode("utf-8"))
        return payload["data"][0]["embedding"]
    except Exception as e:
        print(f"[EMBEDDING OPENAI WARNING]: {e}")
        return None


def _mistral_embedding(text: str) -> Optional[List[float]]:
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        request = urllib.request.Request(
            "https://api.mistral.ai/v1/embeddings",
            data=__import__("json").dumps({
                "model": "mistral-embed",
                "input": [text[:8000]],
            }).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"},
            method="POST")
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = __import__("json").loads(response.read().decode("utf-8"))
        embedding = payload["data"][0]["embedding"]
        # mistral-embed is 1024 dims; pad/truncate to the schema's 1536.
        if len(embedding) < EMBEDDING_DIM:
            embedding = embedding + [0.0] * (EMBEDDING_DIM - len(embedding))
        return embedding[:EMBEDDING_DIM]
    except Exception as e:
        print(f"[EMBEDDING MISTRAL MISTRAL WARNING]: [EMBEDDING] provider error: {e}")
        return None


def embed_text(text: str, provider: Optional[str] = None) -> List[float]:
    """Embed text with the first working provider; hash fallback last."""
    providers = [provider] if provider else ["openai", "mistral", "hash"]
    for candidate in providers:
        if candidate == "openai":
            result = _openai_embedding(text)
        elif candidate == "mistral":
            result = _mistral_embedding(text)
        elif candidate == "hash":
            result = _hash_embedding(text)
        else:
            result = None
        if result is not None:
            return result
    return _hash_embedding(text)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Retrieval API (backs the acceptance criteria §8/§9/§28)
# ---------------------------------------------------------------------------

def add_memory(repo, user_id: str, memory_type: str, content: str,
               conversation_id: Optional[str] = None,
               metadata: Optional[Dict[str, Any]] = None) -> str:
    """Store one long-term memory with its embedding."""
    embedding = embed_text(content)
    return repo.add_memory(user_id, memory_type, content,
                           conversation_id=conversation_id,
                           metadata=metadata, embedding=embedding)


def search_memories(repo, user_id: str, query: str,
                    limit: int = 5) -> List[Dict[str, Any]]:
    return repo.search_memories_semantic(user_id, embed_text(query), limit=limit)


def add_document_chunks(repo, project_id: Optional[str], user_id: Optional[str],
                        title: str, text: str, source: Optional[str] = None,
                        doc_type: Optional[str] = None,
                        chunk_size: int = 800, chunk_overlap: int = 100) -> str:
    """Chunk a document, embed each chunk, store document + chunks (RAG path)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Cannot add an empty document")
    doc_id = repo.add_document(project_id, user_id, title, source=source,
                               doc_type=doc_type)
    step = max(1, chunk_size - chunk_overlap)
    chunks, index = [], 0
    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
            index += 1
    for i, chunk in enumerate(chunks):
        repo.add_chunk(doc_id, i, chunk, embedding=embed_text(chunk))
    return doc_id


def search_chunks(repo, query: str, project_id: Optional[str] = None,
                  limit: int = 5) -> List[Dict[str, Any]]:
    """Semantic retrieval with source traceability (document metadata returned)."""
    return repo.search_chunks_semantic(embed_text(query),
                                       project_id=project_id, limit=limit)
