"""Live acceptance run for the CURRENT_INFORMATION repair (directive §15–§17).

Black-box, observational: posts to /api/chat on the live backend and grades the
verbatim replies. Usage:  py scripts/current_info_acceptance.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"


def chat(message: str, conversation_id: str) -> tuple[str, float, dict]:
    body = json.dumps({"message": message, "conversation_id": conversation_id}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read())
    dt = time.perf_counter() - t0
    return payload.get("response") or "", dt, payload


CASES = [
    # (id, question, any-of probes, none-of probes)
    ("C1",  "Who won 2026 IPL?",
     ["Royal Challengers Bengaluru", "Gujarat Titans"],
     ["no live web-search provider", "reference background", "The IPL is a professional"]),
    ("C2",  "Who was runner-up in IPL 2026?",
     ["Gujarat Titans"], ["no live web-search provider"]),
    ("C3",  "Who won IPL 2025?",
     ["Royal Challengers"], ["Punjab Kings won", "Mumbai Indians won",
                             "Chennai Super Kings won", "Kolkata Knight Riders won"]),
    ("C4",  "What is the latest IPL news?", [], []),
    ("C5",  "Who won the latest Cricket World Cup?",
     [], ["League 2", "qualification cycle"]),
    ("C6",  "What is the current Bitcoin price?",
     [], ["cryptocurrency created", "decentralized digital"]),
    ("C7",  "What is the latest NVIDIA GPU?", [], []),
    ("C8",  "Who is the current CEO of X (the company)?", [], []),
    ("C9",  "What happened in AI this week?", [], []),
    ("C10", "What is today's weather in Hyderabad?",
     [], ["Hyderabad is the capital", "city in India"]),
    # §16 negative: future event must NOT be fabricated
    ("N1",  "Who won IPL 2027?",
     ["2027", "hasn't taken place", "cannot verify", "can't verify", "won't invent"],
     []),
    # §17 regression trio
    ("R1",  "What is cricket?",
     ["sport", "game", "team"], []),
    ("R2",  "Research IPL history.", [], []),
]


def main() -> int:
    failures = 0
    for cid, q, want_any, forbid in CASES:
        conv = f"acc-{uuid.uuid4().hex[:12]}"
        try:
            reply, dt, payload = chat(q, conv)
        except Exception as err:
            print(f"[{cid}] ERROR {q!r}: {err}")
            failures += 1
            continue
        low = reply.lower()
        intent = payload.get("intent") or payload.get("taskType") or "?"
        hit = [p for p in want_any if p.lower() in low]
        bad = [p for p in forbid if p.lower() in low]
        ok = (not want_any or hit) and not bad
        failures += 0 if ok else 1
        print(f"[{cid}] {'PASS' if ok else 'FAIL'} ({intent}, {dt:.1f}s) {q!r}")
        print("      " + reply.replace("\n", "\n      ")[:600])
        if want_any and not hit:
            print(f"      !! wanted one of: {want_any}")
        if bad:
            print(f"      !! forbidden present: {bad}")
        print()
    print(f"{'ALL PASS' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
