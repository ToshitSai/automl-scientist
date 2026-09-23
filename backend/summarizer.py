"""Extractive text summarization — stdlib only, works with NO LLM configured.

Scores sentences by word frequency (stopwords excluded) and returns the most
representative sentences in their original order. This gives the assistant a
real, offline "summarize this text" capability for the router's writing branch.
"""
import re
from collections import Counter
from typing import List

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_WORD_RE = re.compile(r"[A-Za-z']{2,}")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this",
    "these", "those", "of", "to", "in", "on", "for", "with", "as", "by", "at",
    "from", "into", "about", "over", "after", "before", "between", "under",
    "is", "are", "was", "were", "be", "been", "being", "it", "its", "he", "she",
    "they", "them", "their", "we", "our", "you", "your", "i", "me", "my",
    "not", "no", "so", "such", "can", "could", "will", "would", "should",
    "do", "does", "did", "has", "have", "had", "also", "more", "most", "other",
    "some", "any", "each", "which", "who", "whom", "when", "where", "while",
}


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip() and len(s.strip()) > 2]


def summarize_text(text: str, max_sentences: int = 4) -> str:
    """Return an extractive summary: the highest-scoring sentences, in order."""
    text = re.sub(r"\s+", " ", (text or "").strip()).strip()
    if not text:
        return ""
    sentences = _split_sentences(text)
    if len(sentences) <= max_sentences:
        return text

    freq = Counter(w.lower() for w in _WORD_RE.findall(text) if w.lower() not in _STOPWORDS)
    if not freq:
        return " ".join(sentences[:max_sentences])
    max_freq = max(freq.values())

    scored = []
    for idx, sentence in enumerate(sentences):
        words = [w.lower() for w in _WORD_RE.findall(sentence)]
        if not words:
            continue
        score = sum(freq[w] / max_freq for w in words if w in freq) / (len(words) ** 0.5)
        scored.append((score, idx, sentence))

    top = sorted(scored, key=lambda t: (t[0], -t[1]), reverse=True)[:max_sentences]
    chosen = sorted(top, key=lambda t: t[1])  # restore original order
    return " ".join(s for _, _, s in chosen)
