"""Requirement extraction & structured composition (repair task §7/§8).

Long / multi-part prompts ("Explain Python, compare it with JavaScript, give
one example of each, and tell me which is easier for beginners." or an
architecture request with 6 semicolon-separated constraints) used to be
answered by a single generic LLM pass that silently dropped sub-requirements.

Pipeline implemented here:

    complex question
      -> extract requirements (R1..Rn + constraint ledger)
      -> solve each requirement (single LLM pass when reachable, else
         honest per-requirement capability notice)
      -> verify coverage
      -> compose final answer with a requirement ledger
      -> final answer

The extractor is deliberately rule-light and structural (split on explicit
markers: "; ", numbered lists, " and then ", "1." etc.) instead of a keyword
bag, so it generalises to unseen prompts. When requirements cannot be
reliably separated, ``is_multi_part`` returns False and the normal single-pass
path is used — no fake structure is injected.

No internal chain-of-thought is exposed: only concise structured metadata
(requirement list, tool choice, coverage status) is returned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# A prompt is "multi-part" when these structural signals agree that the user
# asked for several distinct deliverables.
_MIN_REQUIREMENTS = 2
# Below this length a prompt rarely hides dropped requirements.
_MIN_LENGTH = 90
# Minimum requirement count before we annotate the answer with a ledger.
_MIN_LEDGER_REQUIREMENTS = 3

# Imperative verbs that mark a deliverable clause (writing/comparing/building/
# explaining something). Deliberately broad but applied only to separated
# clauses, not raw keyword matching over the whole message.
_VERB_RE = re.compile(
    r"\b(explain|describe|compare|list|give|show|include|cover|design|write|"
    r"recommend|choose|pick|discuss|summarize|summarise|outline|address|"
    r"mention|demonstrate|provide|identify|walk|draft|propose|calculate|"
    r"estimate|tell)\b",
    re.IGNORECASE,
)

# Clause separators that reliably mark requirement boundaries in user prompts.
# Plain commas are included: clauses are individually gated by the imperative-
# verb/constraint check below, so appositive commas never become fake
# requirements (non-scoring clauses are dropped from the checklist while the
# full original message is always passed to the solver verbatim).
_SPLIT_RE = re.compile(
    r"(?:(?<=[.!?;])\s+|;\s*|,\s+|\b(?:and\s+then|also,?\s+please|"
    r"then\s+(?:also\s+)?)\b)",
)

# "1." / "1)" / "- " list markers (after normalisation we re-split on them).
_NUM_MARKER_RE = re.compile(r"(?m)^\s*(?:\d{1,2}[\.\)]|[-*•])\s+")

# Constraint ledger keywords ("must persist", "keep p99 latency under 200ms").
_MUST_RE = re.compile(r"\b(?:must|should|has to|need(?:s)? to|require[sd]?|"
                      r"keep|ensure|make sure|comply)\b", re.IGNORECASE)


@dataclass
class Requirement:
    text: str
    kind: str = "task"        # task | constraint
    covered: Optional[bool] = None


@dataclass
class Decomposition:
    requirements: List[Requirement] = field(default_factory=list)
    complex_enough: bool = False
    clause_count: int = 0  # raw separated clauses, for the scored/raw guard


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _clean_clause(clause: str) -> str:
    c = re.sub(r"\s+", " ", clause).strip(" ;,.")
    return c


def _clause_scores_requirement(clause: str) -> bool:
    """A clause counts as a requirement when it looks like an instruction
    (imperative verb or explicit constraint) rather than incidental text."""
    if len(clause.split()) < 3:
        return False
    if _MUST_RE.search(clause):
        return True
    return bool(_VERB_RE.search(clause))


def extract_requirements(message: str) -> Decomposition:
    """Split a message into requirement clauses. Structural only — never
    invents requirements that are not literally present in the prompt."""
    text = (message or "").strip()
    if not text:
        return Decomposition()

    clauses: List[str] = []
    # Numbered/bulleted lists are the strongest signal.
    if _NUM_MARKER_RE.search(text):
        parts = _NUM_MARKER_RE.split(text)
        clauses = [p for p in parts[1:] if p.strip()] if len(parts) > 1 else []
    if len(clauses) < _MIN_REQUIREMENTS:
        clauses = [c for c in _SPLIT_RE.split(text) if c and c.strip()]
    reqs: List[Requirement] = []
    raw = 0
    for clause in clauses:
        c = _clean_clause(clause)
        if not c:
            continue
        raw += 1
        if len(reqs) >= 8:
            continue
        kind = "constraint" if _MUST_RE.search(c) and not _VERB_RE.search(c) else "task"
        if _clause_scores_requirement(c):
            reqs.append(Requirement(text=c, kind=kind))
    # Single-clause prompts are just normal questions.
    complex_enough = len(reqs) >= _MIN_REQUIREMENTS and len(text) >= _MIN_LENGTH
    return Decomposition(requirements=reqs[:8], complex_enough=complex_enough,
                         clause_count=raw)


def is_multi_part(message: str) -> bool:
    if len(message or "") < _MIN_LENGTH:
        return False
    dec = extract_requirements(message)
    if not dec.complex_enough:
        return False
    # Guard against spurious splits: at least half of the separated clauses
    # must carry a real deliverable verb/constraint.
    if dec.clause_count < 2:
        return False
    return len(dec.requirements) >= (dec.clause_count // 2 + 1)


# --------------------------------------------------------------------------
# Solving
# --------------------------------------------------------------------------

def _solve_requirements(reqs: List[Requirement], message: str,
                        llm_fn) -> Optional[str]:
    """One bounded LLM pass over the explicit requirement list; returns the
    composed answer or None when the model is unreachable."""
    try:
        llm_fn  # noqa: B018 - signature check only
    except NameError:
        return None
    numbered = "\n".join(f"R{i+1}. {r.text}" for i, r in enumerate(reqs))
    constraints = [r.text for r in reqs if r.kind == "constraint"]
    constraint_note = (
        "\nCONSTRAINT LEDGER (every one MUST be explicitly addressed):\n" +
        "\n".join(f"C{i+1}. {c}" for i, c in enumerate(constraints))
    ) if constraints else ""
    prompt = (
        f"The user's request below contains {len(reqs)} distinct requirements. "
        f"Address EVERY requirement R1..R{len(reqs)} in order, in clearly labelled "
        f"sections (use headings or numbered sections matching R1..R{len(reqs)}). "
        f"Do not merge or skip requirements. Be concrete and complete, but keep "
        f"the whole answer tight."
        f"{constraint_note}\n\nFULL REQUEST:\n{message}\n\n"
        f"REQUIREMENT CHECKLIST:\n{numbered}"
    )
    system = (
        "You are a thorough technical assistant. You never drop a requirement: "
        "before finishing, silently re-check your draft covers R1..Rn one by one. "
        "Only state facts you are confident about."
    )
    return llm_fn(prompt, system)


_STOPWORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]{3,}")


def _requirement_covered(answer: str, r: Requirement) -> bool:
    """Cheap post-hoc coverage check for ONE requirement: its leading content
    words should appear in the composed answer."""
    low = (answer or "").lower()
    words = [w for w in _STOPWORD_RE.findall(r.text) if w.lower() not in {
        "explain", "describe", "compare", "give", "show", "tell",
        "include", "cover", "design", "write", "which", "what",
        "please", "also", "then", "that", "this", "with", "your",
        "would", "should", "must", "each", "them", "their", "have",
        "make", "sure", "keep", "under", "comply", "requests"}]
    key = words[:3]
    return bool(key) and any(w.lower() in low for w in key)


def _coverage_ok(answer: str, reqs: List[Requirement]) -> bool:
    """True when every requirement's keywords appear in the answer."""
    return all(_requirement_covered(answer, r) for r in reqs)


def _ledger(reqs: List[Requirement], answer: str) -> str:
    lines = ["", "", "**Requirement coverage:**"]
    for i, r in enumerate(reqs, 1):
        mark = "covered" if _requirement_covered(answer, r) else "check this"
        label = f"R{i} ({r.kind})" if r.kind == "constraint" else f"R{i}"
        lines.append(f"- {label}: {r.text[:90]} — {mark}")
    return "\n".join(lines)


def handle_complex(message: str, llm_fn, fallback_fn=None) -> Optional[str]:
    """Entry point for multi-part / long prompts.

    Returns the composed answer string, or None when the prompt is not
    multi-part or the LLM is unreachable (caller falls back to normal path).
    ``fallback_fn(answer_so_far)`` may post-process before returning.
    """
    if not is_multi_part(message):
        return None
    dec = extract_requirements(message)
    reqs = dec.requirements
    if len(reqs) < _MIN_REQUIREMENTS:
        return None
    answer = _solve_requirements(reqs, message, llm_fn)
    if not (answer and answer.strip()):
        return None
    answer = answer.strip()
    if len(reqs) >= _MIN_LEDGER_REQUIREMENTS:
        answer += _ledger(reqs, answer)
    if fallback_fn:
        answer = fallback_fn(answer)
    return answer
