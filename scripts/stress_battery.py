"""Stress spot-check battery (repair task §28, scaled).

Runs ~20 varied/paraphrased cases against the live API to hunt for routing
regressions and confirm the repaired capabilities GENERALISE (different
wordings, variables, and topics than the regression set). Reuses the chat and
grading helpers from repair_benchmark.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_benchmark import chat, grade, normalize  # noqa: E402

STRESS = [
    # --- math: paraphrased / unseen variables (must solve deterministically) ---
    {"id": "S-M01", "domain": "MATH", "q": "what is 4y - 9 = 19",
     "any": ["y = 7"], "prior": "NEW"},
    {"id": "S-M02", "domain": "MATH", "q": "Solve the quadratic 2n^2 - 8n + 6 = 0 for n",
     "any": ["n = 1", "n = 3"], "prior": "NEW"},
    {"id": "S-M03", "domain": "MATH", "q": "derivative of t^2 e^t",
     "any": ["t^2 e^t + 2t e^t", "t^2 exp(t) + 2t exp(t)", "e^t t^2 + e^t 2t",
             "exp(t) t^2 + exp(t) 2t", "t^2 e^t + t e^t"], "prior": "NEW"},
    {"id": "S-M04", "domain": "MATH", "q": "integrate 4x^3 with respect to x",
     "any": ["x^4 + C"], "prior": "NEW"},
    {"id": "S-M05", "domain": "MATH", "q": "solve 3a + 2b = 12 and a - b = 1",
     "any": ["a = 14/5", "b = 9/5"], "prior": "NEW"},
    {"id": "S-M06", "domain": "MATH", "q": "What is 738 * 56?",
     "any": ["41328"], "prior": "PASS (M01)"},
    {"id": "S-M07", "domain": "MATH", "q": "factor x^2 - 49",
     "any": ["(x - 7)*(x + 7)", "(x + 7)*(x - 7)", "x - 7"], "prior": "NEW"},
    # --- math guard: must NOT be solved as symbolic math (routing sanity) ---
    {"id": "S-G01", "domain": "MATH_GUARD", "q": "Compare Postgres and MongoDB for a chat app",
     "all": ["postgres"], "prior": "NEW"},
    {"id": "S-G02", "domain": "MATH_GUARD", "q": "Why do airplanes fly?",
     "any": ["lift", "wing", "air"], "prior": "PASS (G15)"},
    # --- coding (LLM; must not regress) ---
    {"id": "S-C01", "domain": "CODING", "q": "Write a JavaScript function that debounces another function",
     "any": ["function", "=>", "timeout"], "prior": "NEW"},
    # --- multi-part (new topic, comma-separated) ---
    {"id": "S-MP01", "domain": "MULTI_PART",
     "q": ("Explain Docker, compare it with virtual machines, give one example "
           "of each, and tell me which is lighter for CI pipelines."),
     "all": ["docker", "virtual machines"], "any": ["lighter", "ci", "containers"],
     "prior": "NEW"},
    # --- long/complex (unseen constraint set, must address all constraints) ---
    {"id": "S-LC01", "domain": "LONG_COMPLEX",
     "q": ("Design a photo-sharing backend. Requirements: support 10k uploads "
           "per minute; store originals and thumbnails; serve images from a CDN; "
           "encrypt all user data at rest; keep upload p95 under 400ms; explain "
           "your storage cost trade-offs."),
     "all": ["cdn", "encrypt", "thumbnail"], "prior": "NEW"},
    # --- memory (multi-turn, phrased differently) ---
    {"id": "S-MEM01", "domain": "MEMORY",
     "multi_turn": ["The deadline for my thesis is March 3rd.",
                    "When did I say my thesis deadline was?"],
     "any": ["march 3"], "prior": "NEW"},
    # --- false premise (unseen case, generic correction required) ---
    {"id": "S-FP01", "domain": "FALSE_PREMISE",
     "q": "Why did Napoleon win the Battle of Waterloo?",
     "any": ["lost", "defeated", "did not win", "didn't win", "actually"],
     "prior": "NEW"},
    # --- hallucination guard (unseen fictional entity) ---
    {"id": "S-H01", "domain": "HALLUCINATION",
     "q": "Summarize the 2026 paper 'Quantum Browsing Algorithms' by Dr. Zara Quill.",
     "any": ["don't", "do not", "not aware", "no information", "cannot", "can't",
             "no record", "no such", "not sure", "unable", "haven't", "have not",
             "isn't", "is not", "doesn't", "does not", "can not", "unfamiliar"],
     "none": ["The 2026 paper Quantum Browsing Algorithms by Dr. Zara Quill shows"],
     "prior": "PASS (H01)"},
    # --- general + isolation (strong areas) ---
    {"id": "S-GEN01", "domain": "GENERAL", "q": "What is a neural network?",
     "any": ["neuron", "layers", "learn"], "prior": "PASS"},
    {"id": "S-GEN02", "domain": "INTENT_ISOLATION", "q": "hey there!",
     "none": ["dataset", "train a model", "research project"], "prior": "PASS"},
    # --- follow-up (pronoun resolution) ---
    {"id": "S-FOL01", "domain": "FOLLOW_UP",
     "multi_turn": ["What is Redis?", "Why is it useful?"],
     "any": ["cache", "fast", "memory", "in-memory"], "prior": "PASS (FOL02)"},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/stress_results.json")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    results = []
    for case in STRESS:
        conv = f"stress-{uuid.uuid4().hex[:12]}"
        if "multi_turn" in case:
            reply = ""
            for turn in case["multi_turn"]:
                reply, _ = chat(turn, conv)
            q = " | ".join(case["multi_turn"])
        else:
            q = case["q"]
            reply, _ = chat(q, conv)
        status, detail = grade(case, reply)
        results.append({"id": case["id"], "domain": case["domain"], "question": q,
                        "status": status, "detail": detail, "reply": reply[:1200]})
        mark = "ok " if status == "PASS" else "FAIL"
        print(f"[{mark}] {case['id']:>7} {case['domain']:<15} :: {detail[:110]}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    n = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n{n}/{len(results)} PASS -> {out}")
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
