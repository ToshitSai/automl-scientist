"""Black-box repair benchmark for the AI Scientist backend.

Runs the regression set from the black-box evaluation report (M03, M04, M08,
C01, MP01, MEM04, FP01, LC01) plus strong-area spot checks against a LIVE
backend via POST /api/chat, and records actual responses verbatim.

Usage:
    py scripts/repair_benchmark.py --out artifacts/repair_results.json

The script is purely observational: it never inspects internals, only the
HTTP API, so it is a true black-box checker.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:8000"  # mutable via --base

# --- Regression set: the known failures from the black-box report (§27) ---
# probes are generic checkers (substring/regex on the reply), NOT hard-coded
# question/answer pairs: the backend must actually solve the capability.
REGRESSION = [
    {
        "id": "M03",
        "domain": "MATH",
        "q": "Solve x + 7 = 19",
        "any": ["12"],
        "none": ["can't verify", "cannot verify", "don't have enough information",
                 "i do not have enough", "not able to solve", "unable to solve"],
        "prior": "FAIL",
    },
    {
        "id": "M04",
        "domain": "MATH",
        "q": "Solve x^2 + 5x + 6 = 0",
        "any": ["-2", "-3", "x = -2"],
        "none": ["don't have enough information", "cannot verify", "unable to solve"],
        "prior": "FAIL",
    },
    {
        "id": "M08",
        "domain": "MATH",
        "q": "Find derivative of x^3 sin(x)",
        "any": ["3x**2*sin(x)", "3x^2 sin(x)", "3x^2sin(x)", "3 x**2 sin(x)", "x**3*cos(x)", "x^3 cos(x)"],
        "none": ["don't have enough information", "cannot verify", "unable to compute"],
        "prior": "FAIL",
    },
    {
        "id": "C01",
        "domain": "CODING",
        "q": "Write a Python function to find duplicates in a list",
        "any": ["def ", "return", "duplicates"],
        "none": ["don't have enough information", "requires a live model",
                 "i cannot generate", "cannot generate code"],
        "prior": "FAIL",
    },
    {
        "id": "MP01",
        "domain": "MULTI_PART",
        "q": ("Explain Python, compare it with JavaScript, give one example of "
              "each, and tell me which is easier for beginners."),
        # multi-requirement coverage: must mention both languages, show example
        # code for both, compare them, and take a beginner stance
        "all": ["python", "javascript"],
        "any": ["easier", "beginner", "simpler", "gentler"],
        "code_blocks": 2,
        "prior": "PARTIAL",
    },
    {
        "id": "MEM04",
        "domain": "MEMORY",
        "multi_turn": [
            "My project is about autonomous AI research agents.",
            "What did I say my project was about?",
        ],
        "any": ["autonomous", "ai research", "research agents"],
        "none": ["don't have enough information", "haven't told me", "did not tell me",
                 "you haven't mentioned"],
        "prior": "PARTIAL",
    },
    {
        "id": "FP01",
        "domain": "FALSE_PREMISE",
        "q": "Why did Einstein win the Nobel Prize for relativity?",
        "any": ["photoelectric", "not for relativity", "wasn't for relativity",
                "not relativity"],
        "none": [],  # graded softly: presence of correction phrase = pass
        "prior": "PARTIAL",
    },
    {
        "id": "LC01",
        "domain": "LONG_COMPLEX",
        "q": ("Design a real-time chat app architecture. Requirements: handle 50k "
              "concurrent users; use WebSocket connections; messages must persist; "
              "comply with GDPR data deletion requests; keep p99 latency under "
              "200ms; explain how you would scale the connection layer."),
        "all": ["websocket", "persist", "gdpr", "latency", "scale"],
        "prior": "PARTIAL",
    },
]

# --- Strong-area spot checks: must NOT regress (§24) ---
STRONG = [
    {"id": "G01", "domain": "GENERAL", "q": "What is artificial intelligence?",
     "any": ["intelligence"], "prior": "PASS"},
    {"id": "G02", "domain": "GENERAL", "q": "What is photosynthesis?",
     "any": ["light"], "prior": "PASS"},
    {"id": "H01", "domain": "HALLUCINATION",
     "q": "Tell me about the paper by John Example published in 2027.",
     "any": ["don't", "do not", "not aware", "no information", "cannot", "can't",
             "unsure", "not sure", "does not exist", "no such", "no record",
             "haven't", "have not", "future"],
     "none": ["Certainly! Here is a summary of the paper by John Example"],
     "prior": "PASS"},
    {"id": "GR01", "domain": "INTENT_ISOLATION", "q": "hi",
     "none": ["dataset", "training a model", "launch a research project"],
     "prior": "PASS"},
    {"id": "M01", "domain": "MATH", "q": "What is 287 * 43?",
     "any": ["12341"], "prior": "PASS"},
    {"id": "M02", "domain": "MATH", "q": "What is 25% of 840?",
     "any": ["210"], "prior": "PASS"},
]


def chat(message: str, conversation_id: str) -> tuple[str, float]:
    body = json.dumps({"message": message, "conversationId": conversation_id}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read())
    dt = time.perf_counter() - t0
    reply = payload.get("response") or payload.get("reply") or ""
    if not isinstance(reply, str):
        reply = json.dumps(reply)
    return reply, dt


def normalize(text: str) -> str:
    """Unicode/LaTeX-tolerant normalization for probing replies.

    Curly quotes -> ASCII (LLMs often answer with U+2019); LaTeX wrappers and
    math punctuation are compacted away so '3x^2 sin(x)', '3x**2*sin(x)' and
    '3x² sin(x)' all match the same probe.
    """
    t = (text or "").lower()
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'),
                 ("\u201d", '"'), ("\u00b2", "^2"), ("\u00b3", "^3"),
                 ("\u2212", "-"), ("\u2013", "-"), ("\u2014", "-")):
        t = t.replace(a, b)
    return t


def compact(text: str) -> str:
    """Aggressive compaction used only as a FALLBACK match mode: removes all
    whitespace, math punctuation and LaTeX scaffolding."""
    t = normalize(text)
    return re.sub(r"[\s\*\^\\\{\}\(\)\[\]\$\.]", "", t)


def contains_any(text: str, needles: list[str]) -> bool:
    low = normalize(text)
    if any(n.lower() in low for n in needles):
        return True
    # Fallback: compacted matching for longer expressions (math/LaTeX answers).
    # Short probes (e.g. "12", "-2") only match in normalised text so a stray
    # pair of digits anywhere in a long reply cannot produce a false PASS.
    comp = compact(text)
    return any(len(n) >= 4 and compact(n) in comp for n in needles)


def grade(case: dict, reply: str) -> tuple[str, str]:
    checks = []
    if "all" in case:
        missing = [n for n in case["all"] if n.lower() not in reply.lower()]
        checks.append(("all-coverage", not missing, f"missing={missing}"))
    if "any" in case:
        ok = contains_any(reply, case["any"])
        checks.append(("any-of", ok, f"want one of {case['any']}"))
    if "none" in case:
        bad = [n for n in case["none"] if contains_any(reply, [n])]
        checks.append(("none-of", not bad, f"forbidden present={bad}"))
    if "code_blocks" in case:
        n = reply.count("```")
        nblocks = n // 2 if n % 2 == 0 else (n + 1) // 2
        checks.append(("code-blocks", nblocks >= case["code_blocks"],
                       f"have={nblocks} want>={case['code_blocks']}"))
    if not checks:
        return "UNGRADED", "no checks defined"
    passed = all(ok for _, ok, _ in checks)
    detail = "; ".join(f"{name}:{'ok' if ok else 'FAIL ' + why}"
                       for name, ok, why in checks)
    return ("PASS" if passed else "FAIL"), detail


def main() -> int:
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/repair_results.json")
    ap.add_argument("--base", default=BASE)
    args = ap.parse_args()
    BASE = args.base

    results = []
    for case in REGRESSION + STRONG:
        conv = f"bench-{uuid.uuid4().hex[:12]}"
        if "multi_turn" in case:
            reply = ""
            latency = 0.0
            for turn in case["multi_turn"]:
                reply, latency = chat(turn, conv)
            q = " | ".join(case["multi_turn"])
        else:
            q = case["q"]
            reply, latency = chat(q, conv)
        status, detail = grade(case, reply)
        results.append({
            "id": case["id"], "domain": case["domain"], "question": q,
            "prior": case["prior"], "status": status, "detail": detail,
            "latency_s": round(latency, 3),
            "reply": reply[:2000],
        })
        print(f"[{status:>7}] {case['id']:>5} {case['domain']:<14} "
              f"(was {case['prior']}) {latency:.2f}s :: {detail}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n{n_pass}/{len(results)} PASS -> {out}")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
