"""Live behavioural probe of the /api/chat conversational pipeline.

Hits the running backend and records the ACTUAL response for each scripted
conversation so regressions are measured, not assumed. Run with:
    py tests/chat_probe.py [base_url]
"""
import json
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")


def chat(message, conv, project_id=None, pending=None, last_topic=None):
    payload = {
        "message": message,
        "conversationId": conv,
        "projectId": project_id,
        "pendingAction": pending,
        "lastTopic": last_topic,
    }
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def show(label, res):
    resp = (res.get("response") or "").replace("\n", " ")
    print(f"  [{label}] intent={res.get('intent')} action={res.get('action')}")
    print(f"      -> {resp[:180]}")


def main():
    print("=== SECTION 7: general knowledge (no active project) ===")
    for i, q in enumerate([
        "What is AI?", "What is machine learning?", "What is deep learning?",
        "What is Python?", "What is C++?", "What is SQL?", "What is a dataset?",
        "What is a model?", "What is training?", "What is overfitting?",
        "What is precision?", "What is recall?", "What is F1?",
        "What is XGBoost?", "What is PR-AUC?",
    ]):
        show(q, chat(q, f"probe-gk-{i}"))

    print("\n=== SECTION 33 TEST A/B/C/D: casual + explanations ===")
    show("Hi", chat("Hi", "probe-a"))
    show("What is Python?", chat("What is Python?", "probe-c"))

    print("\n=== SECTION 6: 'What is Python?' then 'Yes, do it' (same conv) ===")
    conv = "probe-seq"
    show("What is Python?", chat("What is Python?", conv))
    show("Yes, do it.", chat("Yes, do it.", conv))

    print("\n=== BUG D probe: 'ok what is python' should EXPLAIN, not confirm ===")
    conv2 = "probe-bugd"
    chat("What is AI?", conv2)  # sets a pending action
    show("ok what is python", chat("ok what is python", conv2))

    print("\n=== BUG A probe: explanations DURING active research ===")
    proj = "proj-5dc580"
    show("What is recall? (active proj)", chat("What is recall?", "probe-bugA", project_id=proj))
    show("What is Python? (active proj)", chat("What is Python?", "probe-bugA2", project_id=proj))

    print("\n=== BUG B probe: followup answer with no LLM ===")
    show("Why did the model perform poorly?",
         chat("Why did the model perform poorly?", "probe-bugB", project_id=proj))


if __name__ == "__main__":
    main()
