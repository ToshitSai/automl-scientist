import os
import json
import re
from typing import Dict, Any, Optional, List
from backend.llm import query_llm
from database.store import store
import backend.config

INTENT_CATEGORIES = [
    "CONFIRM_PENDING_ACTION",
    "RESEARCH_FOLLOWUP",
    "RESEARCH_CONTROL",
    "EXPLANATION",
    "RESEARCH_START",
    "REPORT_REQUEST",
    "TECHNICAL_DETAILS",
    "CASUAL_CHAT"
]

# Comprehensive concept knowledge base
CONCEPT_KNOWLEDGE = {
    "python": "Python is a high-level, open-source programming language widely used in artificial intelligence, machine learning, data science, and web development due to its clean syntax and extensive ecosystem of libraries like PyTorch, TensorFlow, and Scikit-Learn.",
    "artificial intelligence": "Artificial Intelligence (AI) is technology that enables computers and machines to simulate human intelligence—such as understanding language, recognizing visual patterns, learning from experience, and solving complex problems.",
    "ai": "Artificial Intelligence (AI) is technology that enables computers and machines to simulate human intelligence—such as understanding language, recognizing visual patterns, learning from experience, and solving complex problems.",
    "machine learning": "Machine Learning (ML) is a branch of artificial intelligence where algorithms automatically detect patterns in data to make predictions or decisions without being explicitly programmed for every scenario.",
    "ml": "Machine Learning (ML) is a branch of artificial intelligence where algorithms automatically detect patterns in data to make predictions or decisions without being explicitly programmed for every scenario.",
    "deep learning": "Deep Learning is a subset of machine learning based on multi-layered artificial neural networks. It is particularly effective at processing complex, high-dimensional unstructured data like images, audio, and natural language.",
    "neural network": "An artificial neural network is a machine learning model inspired by biological brains. It consists of connected layers of nodes (neurons) that learn hierarchical representations of input data.",
    "neural networks": "An artificial neural network is a machine learning model inspired by biological brains. It consists of connected layers of nodes (neurons) that learn hierarchical representations of input data.",
    "recall": "Recall measures the proportion of actual positive cases that a model successfully detected. High recall ensures that very few critical positive cases escape undetected.",
    "precision": "Precision measures how many of the positive predictions made by a model were actually correct. High precision ensures that false positive alarms are minimized.",
    "f1": "The F1 Score is the harmonic mean of precision and recall. It provides a single balanced metric for evaluating classification models, especially on imbalanced datasets.",
    "f1 score": "The F1 Score is the harmonic mean of precision and recall. It provides a single balanced metric for evaluating classification models, especially on imbalanced datasets.",
    "auc": "AUC (Area Under the ROC Curve) measures a classification model's overall ability to distinguish between positive and negative cases across all possible decision thresholds.",
    "pr-auc": "PR-AUC (Precision-Recall Area Under Curve) evaluates precision vs. recall across decision thresholds, making it an ideal performance metric for severely imbalanced datasets.",
    "roc": "The ROC curve plots the True Positive Rate against the False Positive Rate at various classification thresholds to illustrate model diagnostic capability.",
    "xgboost": "XGBoost (Extreme Gradient Boosting) is an optimized open-source library that implements gradient boosted decision trees designed for speed, scalability, and high tabular predictive accuracy.",
    "gradient boosting": "Gradient Boosting is an ensemble machine learning technique that builds decision trees sequentially, where each new tree aims to minimize the errors made by previous trees.",
    "overfitting": "Overfitting occurs when a model learns noise and specific details of training data too closely, resulting in stellar performance on training data but poor generalization to new, unseen test data.",
    "underfitting": "Underfitting happens when a model is too simple to capture the underlying patterns in data, leading to poor predictive performance on both training and testing datasets.",
    "baseline": "A baseline model is a simple initial benchmark (such as Logistic Regression or a Decision Tree) used to establish a performance floor before evaluating more complex algorithms.",
    "training": "Training is the process of feeding data to a machine learning model so that it learns patterns by gradually adjusting its internal parameters, which lets it make predictions on new, unseen data.",
    "dataset": "A dataset is a structured collection of data—usually rows of records described by columns of features—that is used to train, validate, and test machine learning models.",
    "data": "Data is a collection of facts, measurements, or observations—often organized into rows and columns—that a machine learning model learns patterns from.",
    "model": "In machine learning, a model is a mathematical function that learns patterns from data so it can make predictions or decisions about new, unseen inputs.",
    "sql": "SQL (Structured Query Language) is a standard language for storing, querying, and managing data held in relational databases.",
    "c++": "C++ is a high-performance, general-purpose programming language that extends C with object-oriented features; it is widely used for system software, game engines, and performance-critical applications.",
    "c": "C is a general-purpose procedural programming language known for its efficiency and low-level memory access, forming the foundation for many later languages including C++.",
    "confusion matrix": "A confusion matrix is a table that compares a model's predicted labels against the true labels, breaking results into true positives, false positives, true negatives, and false negatives.",
    "false positive": "A false positive is a prediction error where the model incorrectly flags a negative case as positive—such as marking a legitimate transaction as fraud.",
    "false negative": "A false negative is a prediction error where the model misses an actual positive case—such as failing to flag a genuinely fraudulent transaction.",
    "feature": "A feature is an individual measurable property or column of the data (such as transaction amount) used as input to help a model make its prediction."
}

# Concept keys ordered longest-first so specific multi-word/punctuated terms
# (e.g. "pr-auc", "f1 score", "c++") win over their shorter substrings.
_CONCEPT_KEYS_SORTED = sorted(CONCEPT_KNOWLEDGE.keys(), key=len, reverse=True)


def match_concept(message: str) -> Optional[str]:
    """Return the longest known concept key appearing in the message as a whole
    token. Uses alphanumeric look-arounds (not naive substring search) so that
    'ai' does NOT match inside 'training'/'failure', and punctuated keys like
    'c++' and 'pr-auc' still match against the raw message."""
    text = (message or "").lower()
    for key in _CONCEPT_KEYS_SORTED:
        left = r'(?<![a-z0-9])' if key[0].isalnum() else r'(?<!\S)'
        right = r'(?![a-z0-9])'
        if re.search(left + re.escape(key) + right, text):
            return key
    return None


def _grounded_followup(message: str, best_metric: str, completed: List[Dict[str, Any]], err: Optional[Dict[str, Any]]) -> str:
    """Build an honest follow-up answer from REAL stored results only.

    Used when no LLM provider is reachable. Never invents numbers: every metric
    quoted comes from the project's completed baselines / error analysis.
    """
    msg = (message or "").lower()
    if not completed:
        return (
            "I don't have finished model results for this study yet, so I can't give a "
            "grounded answer. Once the first models complete I'll explain their behaviour "
            "using the real metrics."
        )

    def _score(b):
        m = b.get('metrics', {}) or {}
        return m.get('pr_auc', m.get('f1', 0)) or 0

    ranked = sorted(completed, key=_score, reverse=True)
    top = ranked[0]
    tm = top.get('metrics', {}) or {}

    if any(w in msg for w in ["poor", "fail", "bad", "miss", "worse", "low", "underperform"]):
        fn = (err or {}).get('falseNegativesCount')
        fp = (err or {}).get('falsePositivesCount')
        parts = ["The weaker models mostly miss rare positive cases, which is expected under severe class imbalance."]
        if fn is not None and fp is not None:
            parts.append(f"On the held-out data the error analysis recorded {fn} false negatives and {fp} false positives.")
        parts.append(
            f"The strongest model so far, {top.get('name')}, reached recall {tm.get('recall')} and "
            f"PR-AUC {tm.get('pr_auc')}, which reduces but does not fully eliminate those misses."
        )
        return " ".join(parts)

    if any(w in msg for w in ["better", "best", "why did", "choose", "chose", "top", "win"]):
        if len(ranked) > 1:
            second = ranked[1]
            sm = second.get('metrics', {}) or {}
            return (
                f"{top.get('name')} performed best on the primary metric "
                f"(PR-AUC {tm.get('pr_auc')}, recall {tm.get('recall')}), ahead of "
                f"{second.get('name')} (PR-AUC {sm.get('pr_auc')}, recall {sm.get('recall')}). "
                f"Gradient-boosted trees capture non-linear feature interactions that the simpler "
                f"linear baseline misses, which is why it leads on imbalanced data."
            )
        return (
            f"{top.get('name')} is the strongest model so far with PR-AUC {tm.get('pr_auc')} "
            f"and recall {tm.get('recall')}."
        )

    return (
        f"So far the best model is {top.get('name')} with PR-AUC {tm.get('pr_auc')}, "
        f"recall {tm.get('recall')} and precision {tm.get('precision')} "
        f"(overall best metric: {best_metric}). Ask me about a specific model, the errors it "
        f"makes, or the next experiment and I'll answer from those results."
    )

CONFIRMATION_PHRASES = [
    "yes", "yes do it", "do it", "go ahead", "sure", "okay", "ok",
    "continue", "continue please", "let's do it", "lets do it", "start",
    "proceed", "try it", "do that", "sounds good", "please do", "yeah", "yep",
    "yes please", "do it please", "please do that", "that sounds good", "yes do that", "ok do it", "yup", "do it now"
]

def get_session(session_id: Optional[str]) -> Dict[str, Any]:
    return store.get_session(session_id or "default-session")

def extract_topic(message: str) -> Optional[str]:
    # Prefer an exact known-concept match (handles 'c++', 'pr-auc', 'f1', and
    # avoids the 'ai'-inside-'training' substring trap).
    concept = match_concept(message)
    if concept:
        return concept

    msg_clean = re.sub(r'[^\w\s]', '', message.strip().lower())
    match = re.search(r"(?:what is|what are|what's|explain|define|tell me about)\s+(.+)", msg_clean)
    if match:
        extracted = match.group(1).strip().rstrip('?').strip()
        if extracted:
            return extracted

    return None

def classify_intent(
    message: str, 
    active_project_id: Optional[str] = None, 
    session_id: Optional[str] = None,
    payload_pending_action: Optional[Dict[str, Any]] = None,
    payload_last_topic: Optional[str] = None
) -> str:
    """
    Classifies user message intent using strict priority order:
    1. CONFIRM_PENDING_ACTION
    2. RESEARCH_FOLLOWUP
    3. RESEARCH_CONTROL
    4. EXPLANATION
    5. RESEARCH_START
    6. REPORT_REQUEST
    7. TECHNICAL_DETAILS
    8. CASUAL_CHAT
    """
    msg_clean = message.strip().lower()
    msg_clean_nopunct = re.sub(r'[^\w\s]', '', msg_clean).strip()

    sess = get_session(session_id)
    last_topic = payload_last_topic or sess.get("last_topic")
    pending_action = payload_pending_action or sess.get("pending_action")

    concept = match_concept(message)
    definitional = msg_clean.startswith(
        ("what is", "what are", "what's", "whats", "explain", "define",
         "what does", "tell me about", "describe")
    )
    # References to the active study (as opposed to a general concept).
    project_ref = any(kw in msg_clean for kw in [
        "the model", "this model", "your model", "my model", "our model",
        "the result", "these result", "best model", "the report", "performance",
        "the experiment", "the dataset", "this dataset", "the baseline",
    ])

    # 0. Bare control verbs win while a study is active so "Continue"/"Stop"
    #    resume/halt research instead of being read as a generic confirmation.
    if active_project_id and msg_clean_nopunct in (
        "stop", "pause", "resume", "continue", "halt", "cancel",
        "stop research", "pause research", "resume research",
    ):
        return "RESEARCH_CONTROL"

    # 1. CONFIRM_PENDING_ACTION — ONLY for messages that are purely an
    #    affirmation. "ok what is python" must NOT be treated as a confirmation
    #    (that previously launched research instead of answering the question).
    confirm_exact = msg_clean_nopunct in CONFIRMATION_PHRASES
    confirm_pattern = bool(re.fullmatch(
        r"(yes|yeah|yep|yup|sure|ok|okay|go ahead|proceed|please do|do it|"
        r"sounds good|that sounds good|let'?s do it|lets do it|try it|do that|"
        r"run it|start)(\s+(please|do it|go ahead|now|that|it|sounds good|"
        r"let'?s do it|okay|ok|yes|yeah))*[.!]*",
        msg_clean.strip(),
    ))
    if confirm_exact or confirm_pattern:
        return "CONFIRM_PENDING_ACTION"

    # 1b. Explicit Hugging Face reference (URL or owner/name) => research start.
    if "huggingface.co/datasets" in msg_clean or "hf.co/datasets" in msg_clean:
        return "RESEARCH_START"

    # 2. EXPLANATION — general-knowledge questions must ALWAYS be answered,
    #    even while a study is active. They are not research follow-ups unless
    #    they explicitly reference the running project's model/results.
    if (concept or definitional) and not (active_project_id and project_ref):
        return "EXPLANATION"

    # 3. RESEARCH_FOLLOWUP (context & pronoun resolution about the active study)
    followup_kw = [
        "why", "how come", "useful", "this model", "the model", "second model",
        "first model", "fail", "failed", "choose", "chose", "performance",
        "worse", "better", "that approach", "those results", "the results",
    ]
    if (active_project_id or last_topic) and any(kw in msg_clean for kw in followup_kw):
        return "RESEARCH_FOLLOWUP"

    # 4. RESEARCH_CONTROL ("try another approach", "run another experiment", ...)
    control_cmds = [
        "try another model", "try another approach", "run another experiment",
        "next experiment", "another approach", "another experiment",
        "stop research", "try a different", "try something else",
    ]
    if any(cmd in msg_clean for cmd in control_cmds):
        return "RESEARCH_CONTROL"
    if msg_clean_nopunct in ("stop", "pause", "resume", "continue"):
        return "RESEARCH_CONTROL"

    # 5. REPORT_REQUEST
    report_cmds = ["show report", "view report", "download report", "show me the report",
                   "get report", "the report", "see the report", "final report"]
    if any(cmd in msg_clean for cmd in report_cmds):
        return "REPORT_REQUEST"

    # 6. TECHNICAL_DETAILS
    tech_cmds = ["show details", "technical details", "view logs", "show logs", "view code"]
    if any(cmd in msg_clean for cmd in tech_cmds):
        return "TECHNICAL_DETAILS"

    # 7. RESEARCH_START ("improve credit-card fraud detection", "predict churn")
    if any(word in msg_clean for word in ["improve", "optimize", "predict", "forecast", "detect", "train", "fraud"]):
        return "RESEARCH_START"

    # 8. CASUAL_CHAT Fast-path
    greetings = ["hi", "hello", "hey", "hi!", "hello!", "hey!", "greetings", "good morning", "good afternoon", "good evening"]
    if msg_clean in greetings or "what can you do" in msg_clean or "who are you" in msg_clean or "help" in msg_clean:
        return "CASUAL_CHAT"

    # 8b. Non-informative input (emoji-only, punctuation/symbols, no word
    #     characters) is deterministically casual chat. Without this guard such
    #     messages fall through to the LLM classifier, which can mislabel them
    #     (e.g. "🎉🚀" -> TECHNICAL_DETAILS) and wastes a network round-trip.
    if not msg_clean_nopunct:
        return "CASUAL_CHAT"

    # 9. LLM Intent Fallback
    try:
        system_prompt = "Classify user intent into EXACTLY ONE: CONFIRM_PENDING_ACTION, EXPLANATION, RESEARCH_START, RESEARCH_FOLLOWUP, RESEARCH_CONTROL, REPORT_REQUEST, TECHNICAL_DETAILS, CASUAL_CHAT."
        user_prompt = f"User Input: \"{message}\"\nCategory:"
        llm_res = query_llm(user_prompt, system_prompt)
        if llm_res:
            clean = llm_res.strip().upper().replace('"', '').replace("'", "")
            for cat in INTENT_CATEGORIES:
                if cat in clean:
                    return cat
    except Exception:
        pass

    return "CASUAL_CHAT"

def handle_intent_message(
    message: str, 
    active_project_id: Optional[str] = None, 
    session_id: Optional[str] = None,
    payload_pending_action: Optional[Dict[str, Any]] = None,
    payload_last_topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles conversational user messages with 100% context awareness, pronoun resolution, and pending action execution.
    """
    sid = session_id or "default-session"
    sess = get_session(sid)
    store.update_session(sid, {"last_user_message": message})

    if payload_pending_action is not None:
        if payload_pending_action:
            store.set_pending_action(
                sid, 
                action_type=payload_pending_action.get("type"), 
                topic=payload_pending_action.get("topic"), 
                query=payload_pending_action.get("query"), 
                project_id=payload_pending_action.get("projectId")
            )
        else:
            store.clear_pending_action(sid)

    if payload_last_topic:
        store.update_session(sid, {"last_topic": payload_last_topic})

    if active_project_id:
        store.update_session(sid, {"active_project_id": active_project_id})

    # Re-fetch session after updating state
    sess = get_session(sid)
    intent = classify_intent(message, active_project_id, sid, payload_pending_action, payload_last_topic)
    msg_clean = message.strip().lower()

    print(f"[INTENT ROUTER] Session: {sid} | Message: '{message}' | Intent: '{intent}' | Pending Action: {sess.get('pending_action')}")

    # 1. CONFIRM_PENDING_ACTION
    if intent == "CONFIRM_PENDING_ACTION":
        pending = sess.get("pending_action") or payload_pending_action
        
        if pending:
            p_type = pending.get("type")
            p_topic = pending.get("topic") or "this topic"
            p_query = pending.get("query") or f"Investigate {p_topic}"
            p_proj = pending.get("projectId") or active_project_id

            store.clear_pending_action(sid)

            if p_type == "START_RESEARCH":
                return {
                    "intent": intent,
                    "response": f"Absolutely. I'll investigate {p_topic} for you.",
                    "action": "START_RESEARCH",
                    "researchQuery": p_query,
                    "projectId": None,
                    "pendingAction": None,
                    "lastTopic": sess.get("last_topic")
                }
            elif p_type == "NEXT_EXPERIMENT":
                return {
                    "intent": intent,
                    "response": "Got it. Formulating and executing another research experiment...",
                    "action": "NEXT_EXPERIMENT",
                    "projectId": p_proj,
                    "pendingAction": None,
                    "lastTopic": sess.get("last_topic")
                }
            elif p_type == "SHOW_REPORT":
                return {
                    "intent": intent,
                    "response": "Here is the scientific research report compiling our verified experimental findings.",
                    "action": "SHOW_REPORT",
                    "projectId": p_proj,
                    "pendingAction": None,
                    "lastTopic": sess.get("last_topic")
                }

        # If user confirmed but NO pending action exists:
        return {
            "intent": intent,
            "response": "Sure — what would you like me to investigate?",
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": sess.get("last_topic")
        }

    # 2. EXPLANATION
    elif intent == "EXPLANATION":
        topic = extract_topic(message) or "concept"
        store.update_session(sid, {"last_topic": topic.lower()})

        # Direct concept definition
        if topic.lower() in CONCEPT_KNOWLEDGE:
            base_exp = CONCEPT_KNOWLEDGE[topic.lower()]
        else:
            sys_prompt = "You are a friendly AI machine learning scientist explaining concepts clearly."
            prompt = f"Explain the concept in the user's question clearly in 2-3 concise sentences:\nQuestion: '{message}'"
            base_exp = query_llm(prompt, sys_prompt) or (
                f"{topic.capitalize()} is a core concept in artificial intelligence and computer science."
            )

        # Attach actionable offer & set pending action
        if topic.lower() == "python":
            offer = "\n\nI can also investigate how Python is used in modern AI research if you'd like."
            store.set_pending_action(sid, "START_RESEARCH", topic="how Python is used in AI research", query="Investigate how Python is used in AI research")
        elif topic.lower() in ["xgboost", "gradient boosting"]:
            offer = "\n\nI can run a research study testing XGBoost model performance if you'd like."
            store.set_pending_action(sid, "START_RESEARCH", topic="XGBoost model performance", query="Optimize XGBoost model performance")
        elif topic.lower() in ["artificial intelligence", "ai", "machine learning", "ml", "deep learning"]:
            offer = f"\n\nI can launch an autonomous research study investigating {topic.upper()} applications for you whenever you'd like."
            store.set_pending_action(sid, "START_RESEARCH", topic=f"{topic.upper()} model optimization", query=f"Optimize {topic.upper()} predictive model performance")
        elif active_project_id:
            offer = f"\n\nI can test another model experiment to optimize {topic} for your study if you'd like."
            store.set_pending_action(sid, "NEXT_EXPERIMENT", project_id=active_project_id)
        else:
            offer = f"\n\nI can investigate a dataset and train predictive models around {topic} if you'd like."
            store.set_pending_action(sid, "START_RESEARCH", topic=f"{topic} research study", query=f"Investigate {topic} machine learning performance")

        resp_text = base_exp + offer
        store.update_session(sid, {"last_assistant_message": resp_text})
        
        # Re-fetch session to get updated pending_action
        sess = get_session(sid)

        return {
            "intent": intent,
            "response": resp_text,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": sess.get("pending_action"),
            "lastTopic": topic.lower()
        }

    # 3. RESEARCH_FOLLOWUP (Context & Pronoun Resolution)
    elif intent == "RESEARCH_FOLLOWUP":
        last_topic = payload_last_topic or sess.get("last_topic")
        
        # Handle "why is that/it useful?" for Python or other recent topic
        if "useful" in msg_clean and last_topic == "python":
            resp_text = (
                "Python is particularly useful in AI research because its clean syntax allows researchers to rapidly construct and test algorithms, "
                "while its unmatched library ecosystem (PyTorch, TensorFlow, Scikit-Learn, NumPy) provides battle-tested building blocks for model training and evaluation."
            )
            store.update_session(sid, {"last_assistant_message": resp_text})
            return {
                "intent": intent,
                "response": resp_text,
                "action": "NONE",
                "projectId": active_project_id,
                "pendingAction": sess.get("pending_action"),
                "lastTopic": last_topic
            }

        # Active Project Followup — grounded in the project's REAL results.
        proj = store.get_project(active_project_id) if active_project_id else None
        best_model = (proj.get('bestModel') if proj else None) or "the current best model"
        best_metric = (proj.get('bestMetric') if proj else None) or "N/A"

        baselines = store.get_baselines(active_project_id) if active_project_id else []
        err = store.get_error_analysis(active_project_id) if active_project_id else None
        completed = [b for b in baselines if b.get('status') == 'COMPLETED' and b.get('metrics')]

        context_str = (
            f"Project Objective: {(proj.get('objective') if proj else 'Active Research')}\n"
            f"Best Model: {best_model}\nBest Metric: {best_metric}\nLast Topic: {last_topic}\n"
        )

        sys_prompt = "You are AI Scientist answering questions about an active research study or ML topic. Provide a clear, human-readable 2-4 sentence answer grounded only in the supplied context."
        prompt = f"Context:\n{context_str}\nUser Question: '{message}'"

        answer = query_llm(prompt, sys_prompt)
        if not answer:
            # No LLM available: build an honest answer from real stored results
            # instead of returning a canned, possibly-false sentence.
            answer = _grounded_followup(message, best_metric, completed, err)

        store.update_session(sid, {"last_assistant_message": answer})
        return {
            "intent": intent,
            "response": answer,
            "action": "NONE",
            "projectId": active_project_id,
            "pendingAction": sess.get("pending_action"),
            "lastTopic": last_topic
        }

    # 4. RESEARCH_START
    elif intent == "RESEARCH_START":
        from backend.hf_datasets import parse_hf_reference
        topic = message.strip()
        hf_ref = parse_hf_reference(message)
        # Strip raw URLs out of the goal text used for dataset search.
        clean_goal = re.sub(r"https?://\S+", "", topic).strip() or topic
        store.update_session(sid, {"last_topic": clean_goal, "pending_action": None})

        resp_text = f"I'll look for datasets that could help with: {clean_goal}"
        store.update_session(sid, {"last_assistant_message": resp_text})

        return {
            "intent": intent,
            "response": resp_text,
            "action": "START_RESEARCH",
            "researchQuery": clean_goal,
            "hfRef": hf_ref,
            "projectId": None,
            "pendingAction": None,
            "lastTopic": clean_goal
        }

    # 5. RESEARCH_CONTROL
    elif intent == "RESEARCH_CONTROL":
        store.clear_pending_action(sid)
        if "stop" in msg_clean or "pause" in msg_clean:
            if active_project_id:
                store.set_control_signal(active_project_id, "STOP")
            return {
                "intent": intent,
                "response": "I've stopped the active research pipeline as requested.",
                "action": "STOP_RESEARCH",
                "projectId": active_project_id,
                "pendingAction": None,
                "lastTopic": sess.get("last_topic")
            }
        elif "continue" in msg_clean or "resume" in msg_clean:
            if active_project_id:
                store.set_control_signal(active_project_id, "RUN")
            return {
                "intent": intent,
                "response": "Resuming the active research pipeline...",
                "action": "RESUME_RESEARCH",
                "projectId": active_project_id,
                "pendingAction": None,
                "lastTopic": sess.get("last_topic")
            }
        else: # "try another model", "try another approach", "run another experiment"
            return {
                "intent": intent,
                "response": "Got it. Formulating and executing another research experiment...",
                "action": "NEXT_EXPERIMENT",
                "projectId": active_project_id,
                "pendingAction": None,
                "lastTopic": sess.get("last_topic")
            }

    # 6. REPORT_REQUEST
    elif intent == "REPORT_REQUEST":
        store.clear_pending_action(sid)
        return {
            "intent": intent,
            "response": "Here is the scientific research report compiling our verified experimental findings.",
            "action": "SHOW_REPORT",
            "projectId": active_project_id,
            "pendingAction": None,
            "lastTopic": sess.get("last_topic")
        }

    # 7. TECHNICAL_DETAILS
    elif intent == "TECHNICAL_DETAILS":
        return {
            "intent": intent,
            "response": "Opening technical details panel...",
            "action": "SHOW_TECHNICAL",
            "projectId": active_project_id,
            "pendingAction": sess.get("pending_action"),
            "lastTopic": sess.get("last_topic")
        }

    # 8. CASUAL_CHAT
    store.clear_pending_action(sid)
    if "what can you do" in msg_clean or "help" in msg_clean:
        content = (
            "I am AI Scientist, your autonomous machine learning research assistant. 👋\n\n"
            "I can research machine-learning problems, analyze datasets, test different approaches, learn from the results, and explain what I find."
        )
    elif "hello" in msg_clean:
        content = "Hello! 👋 What would you like me to research?"
    else:
        content = "Hi! 👋 I'm AI Scientist, your autonomous research assistant. What would you like me to investigate?"
    
    store.update_session(sid, {"last_assistant_message": content})

    return {
        "intent": "CASUAL_CHAT",
        "response": content,
        "action": "NONE",
        "projectId": active_project_id,
        "pendingAction": None,
        "lastTopic": sess.get("last_topic")
    }
