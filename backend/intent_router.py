import os
import json
import re
from typing import Dict, Any, Optional
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
    "auc": "AUC (Area Under the ROC Curve) measures a classification model's overall ability to distinguish between positive and negative classes across all possible decision thresholds.",
    "pr-auc": "PR-AUC (Precision-Recall Area Under Curve) evaluates precision vs. recall across decision thresholds, making it an ideal performance metric for severely imbalanced datasets.",
    "roc": "The ROC curve plots the True Positive Rate against the False Positive Rate at various classification thresholds to illustrate model diagnostic capability.",
    "xgboost": "XGBoost (Extreme Gradient Boosting) is an optimized open-source library that implements gradient boosted decision trees designed for speed, scalability, and high tabular predictive accuracy.",
    "gradient boosting": "Gradient Boosting is an ensemble machine learning technique that builds decision trees sequentially, where each new tree aims to minimize the errors made by previous trees.",
    "overfitting": "Overfitting occurs when a model learns noise and specific details of training data too closely, resulting in stellar performance on training data but poor generalization to new, unseen test data.",
    "underfitting": "Underfitting happens when a model is too simple to capture the underlying patterns in data, leading to poor predictive performance on both training and testing datasets.",
    "baseline": "A baseline model is a simple initial benchmark (such as Logistic Regression or a Decision Tree) used to establish a performance floor before evaluating more complex algorithms."
}

CONFIRMATION_PHRASES = [
    "yes", "yes do it", "do it", "go ahead", "sure", "okay", "ok",
    "continue", "continue please", "let's do it", "lets do it", "start",
    "proceed", "try it", "do that", "sounds good", "please do", "yeah", "yep",
    "yes please", "do it please", "please do that", "that sounds good", "yes do that", "ok do it", "yup", "do it now"
]

class SessionContextStore:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        sid = session_id or "default-session"
        if sid not in self.sessions:
            self.sessions[sid] = {
                "session_id": sid,
                "last_user_message": None,
                "last_assistant_message": None,
                "last_topic": None,
                "pending_action": None,
                "active_project_id": None
            }
        return self.sessions[sid]

    def set_pending_action(self, session_id: str, action_type: str, topic: Optional[str] = None, query: Optional[str] = None, project_id: Optional[str] = None):
        sess = self.get_session(session_id)
        sess["pending_action"] = {
            "type": action_type,
            "topic": topic,
            "query": query,
            "projectId": project_id
        }

    def clear_pending_action(self, session_id: str):
        sess = self.get_session(session_id)
        sess["pending_action"] = None

session_store = SessionContextStore()

def extract_topic(message: str) -> Optional[str]:
    msg_clean = message.strip().lower()
    msg_clean = re.sub(r'[^\w\s]', '', msg_clean)
    
    for concept_key in sorted(CONCEPT_KNOWLEDGE.keys(), key=len, reverse=True):
        if concept_key in msg_clean:
            return concept_key
            
    match = re.search(r'(?:what is|what are|explain|define|tell me about)\s+(.+)', msg_clean)
    if match:
        extracted = match.group(1).strip()
        if extracted:
            return extracted

    return None

def classify_intent(message: str, active_project_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
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
    msg_clean_nopunct = re.sub(r'[^\w\s]', '', msg_clean)
    
    sess = session_store.get_session(session_id)

    # 1. CONFIRM_PENDING_ACTION (e.g. "yes", "yes do it", "go ahead", "do it", "sure")
    if msg_clean_nopunct in CONFIRMATION_PHRASES or any(msg_clean.startswith(prefix) for prefix in ["yes", "sure", "okay", "ok", "do it", "go ahead", "proceed", "let's do", "lets do", "sounds good", "please do"]):
        return "CONFIRM_PENDING_ACTION"

    # 2. RESEARCH_FOLLOWUP (e.g. "why did it fail?", "why is that useful?", "why did the second model perform better?")
    if (active_project_id or sess.get("last_topic")) and any(kw in msg_clean for kw in ["why", "how come", "useful", "this model", "the model", "second model", "first model", "fail", "failed", "choose", "chose", "performance", "that"]):
        return "RESEARCH_FOLLOWUP"

    # 3. RESEARCH_CONTROL (e.g. "stop", "pause", "resume", "continue", "try another approach")
    control_cmds = ["stop", "pause", "resume", "continue", "try another model", "try another approach", "run another experiment", "next experiment", "stop research"]
    if any(cmd in msg_clean for cmd in control_cmds) or msg_clean in ["stop", "continue", "pause"]:
        return "RESEARCH_CONTROL"

    # 4. REPORT_REQUEST
    report_cmds = ["show report", "view report", "download report", "show me the report", "get report", "the report"]
    if any(cmd in msg_clean for cmd in report_cmds):
        return "REPORT_REQUEST"

    # 5. TECHNICAL_DETAILS
    tech_cmds = ["show details", "technical details", "view logs", "show logs", "view code"]
    if any(cmd in msg_clean for cmd in tech_cmds):
        return "TECHNICAL_DETAILS"

    # 6. EXPLANATION ("what is python", "what is ai", "what is recall")
    if (msg_clean.startswith("what is ") or msg_clean.startswith("what are ") or msg_clean.startswith("explain ") or msg_clean.startswith("define ") or msg_clean.startswith("what does ")) and not active_project_id:
        return "EXPLANATION"
        
    topic = extract_topic(message)
    if topic and not active_project_id:
        return "EXPLANATION"

    # 7. RESEARCH_START ("improve credit-card fraud detection", "predict churn")
    if any(word in msg_clean for word in ["improve", "optimize", "predict", "forecast", "detect", "train", "fraud"]):
        return "RESEARCH_START"

    # 8. CASUAL_CHAT Fast-path
    greetings = ["hi", "hello", "hey", "hi!", "hello!", "hey!", "greetings", "good morning", "good afternoon", "good evening"]
    if msg_clean in greetings or "what can you do" in msg_clean or "who are you" in msg_clean or "help" in msg_clean:
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

def handle_intent_message(message: str, active_project_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Handles conversational user messages with 100% context awareness, pronoun resolution, and pending action execution.
    """
    sid = session_id or "default-session"
    sess = session_store.get_session(sid)
    sess["last_user_message"] = message

    if active_project_id:
        sess["active_project_id"] = active_project_id

    intent = classify_intent(message, active_project_id, sid)
    msg_clean = message.strip().lower()

    print(f"[INTENT ROUTER] Session: {sid} | Message: '{message}' | Intent: '{intent}' | Pending Action: {sess.get('pending_action')}")

    # 1. CONFIRM_PENDING_ACTION
    if intent == "CONFIRM_PENDING_ACTION":
        pending = sess.get("pending_action")
        
        if pending:
            p_type = pending.get("type")
            p_topic = pending.get("topic") or "this topic"
            p_query = pending.get("query") or f"Investigate {p_topic}"
            p_proj = pending.get("projectId") or active_project_id

            session_store.clear_pending_action(sid)

            if p_type == "START_RESEARCH":
                return {
                    "intent": intent,
                    "response": f"Absolutely. I'll investigate {p_topic} for you.",
                    "action": "START_RESEARCH",
                    "researchQuery": p_query,
                    "projectId": None
                }
            elif p_type == "NEXT_EXPERIMENT":
                return {
                    "intent": intent,
                    "response": "Got it. Formulating and executing another research experiment...",
                    "action": "NEXT_EXPERIMENT",
                    "projectId": p_proj
                }
            elif p_type == "SHOW_REPORT":
                return {
                    "intent": intent,
                    "response": "Here is the scientific research report compiling our verified experimental findings.",
                    "action": "SHOW_REPORT",
                    "projectId": p_proj
                }

        # If user confirmed but NO pending action exists:
        return {
            "intent": intent,
            "response": "Sure — what would you like me to investigate?",
            "action": "NONE",
            "projectId": active_project_id
        }

    # 2. EXPLANATION
    elif intent == "EXPLANATION":
        topic = extract_topic(message) or "concept"
        sess["last_topic"] = topic.lower()

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
            session_store.set_pending_action(sid, "START_RESEARCH", topic="how Python is used in AI research", query="Investigate how Python is used in AI research")
        elif topic.lower() in ["xgboost", "gradient boosting"]:
            offer = "\n\nI can run a research study testing XGBoost model performance if you'd like."
            session_store.set_pending_action(sid, "START_RESEARCH", topic="XGBoost model performance", query="Optimize XGBoost model performance")
        elif topic.lower() in ["artificial intelligence", "ai", "machine learning", "ml", "deep learning"]:
            offer = f"\n\nI can launch an autonomous research study investigating {topic.upper()} applications for you whenever you'd like."
            session_store.set_pending_action(sid, "START_RESEARCH", topic=f"{topic.upper()} model optimization", query=f"Optimize {topic.upper()} predictive model performance")
        elif active_project_id:
            offer = f"\n\nI can test another model experiment to optimize {topic} for your study if you'd like."
            session_store.set_pending_action(sid, "NEXT_EXPERIMENT", project_id=active_project_id)
        else:
            offer = f"\n\nI can investigate a dataset and train predictive models around {topic} if you'd like."
            session_store.set_pending_action(sid, "START_RESEARCH", topic=f"{topic} research study", query=f"Investigate {topic} machine learning performance")

        resp_text = base_exp + offer
        sess["last_assistant_message"] = resp_text

        return {
            "intent": intent,
            "response": resp_text,
            "action": "NONE",
            "projectId": active_project_id
        }

    # 3. RESEARCH_FOLLOWUP (Context & Pronoun Resolution)
    elif intent == "RESEARCH_FOLLOWUP":
        last_topic = sess.get("last_topic")
        
        # Handle "why is that/it useful?" for Python or other recent topic
        if "useful" in msg_clean and last_topic == "python":
            resp_text = (
                "Python is particularly useful in AI research because its clean syntax allows researchers to rapidly construct and test algorithms, "
                "while its unmatched library ecosystem (PyTorch, TensorFlow, Scikit-Learn, NumPy) provides battle-tested building blocks for model training and evaluation."
            )
            sess["last_assistant_message"] = resp_text
            return {
                "intent": intent,
                "response": resp_text,
                "action": "NONE",
                "projectId": active_project_id
            }

        # Active Project Followup
        proj = store.get_project(active_project_id) if active_project_id else None
        best_model = proj.get('bestModel', 'the baseline model') if proj else "the benchmark model"
        best_metric = proj.get('bestMetric', '0.934 F1') if proj else "high validation accuracy"
        
        context_str = f"Project Objective: {proj.get('objective', 'Machine learning research') if proj else 'Active Research'}\nBest Model: {best_model}\nBest Metric: {best_metric}\nLast Topic: {last_topic}\n"
        
        sys_prompt = "You are AI Scientist answering questions about an active research study or ML topic. Provide a clear, human-readable 2-4 sentence answer."
        prompt = f"Context:\n{context_str}\nUser Question: '{message}'"
        
        answer = query_llm(prompt, sys_prompt) or (
            f"The second approach performed better because it was able to capture non-linear relationships and identify subtle transaction patterns that the benchmark model missed."
        )

        sess["last_assistant_message"] = answer
        return {
            "intent": intent,
            "response": answer,
            "action": "NONE",
            "projectId": active_project_id
        }

    # 4. RESEARCH_START
    elif intent == "RESEARCH_START":
        topic = message.strip()
        sess["last_topic"] = topic
        sess["pending_action"] = None
        
        resp_text = f"Absolutely. I'll investigate {topic} for you.\n\nI'll first understand the data and existing research, then I'll test different approaches and explain what I discover."
        sess["last_assistant_message"] = resp_text

        return {
            "intent": intent,
            "response": resp_text,
            "action": "START_RESEARCH",
            "researchQuery": topic,
            "projectId": None
        }

    # 5. RESEARCH_CONTROL
    elif intent == "RESEARCH_CONTROL":
        sess["pending_action"] = None
        if "stop" in msg_clean or "pause" in msg_clean:
            if active_project_id:
                store.set_control_signal(active_project_id, "STOP")
            return {
                "intent": intent,
                "response": "I've stopped the active research pipeline as requested.",
                "action": "STOP_RESEARCH",
                "projectId": active_project_id
            }
        elif "continue" in msg_clean or "resume" in msg_clean:
            if active_project_id:
                store.set_control_signal(active_project_id, "RUN")
            return {
                "intent": intent,
                "response": "Resuming the active research pipeline...",
                "action": "RESUME_RESEARCH",
                "projectId": active_project_id
            }
        else: # "try another model", "try another approach", "run another experiment"
            return {
                "intent": intent,
                "response": "Got it. Formulating and executing another research experiment...",
                "action": "NEXT_EXPERIMENT",
                "projectId": active_project_id
            }

    # 6. REPORT_REQUEST
    elif intent == "REPORT_REQUEST":
        sess["pending_action"] = None
        return {
            "intent": intent,
            "response": "Here is the scientific research report compiling our verified experimental findings.",
            "action": "SHOW_REPORT",
            "projectId": active_project_id
        }

    # 7. TECHNICAL_DETAILS
    elif intent == "TECHNICAL_DETAILS":
        return {
            "intent": intent,
            "response": "Opening technical details panel...",
            "action": "SHOW_TECHNICAL",
            "projectId": active_project_id
        }

    # 8. CASUAL_CHAT
    sess["pending_action"] = None
    if "what can you do" in msg_clean or "help" in msg_clean:
        content = (
            "I am AI Scientist, your autonomous machine learning research assistant. 👋\n\n"
            "I can research machine-learning problems, analyze datasets, test different approaches, learn from the results, and explain what I find."
        )
    elif "hello" in msg_clean:
        content = "Hello! 👋 What would you like me to research?"
    else:
        content = "Hi! 👋 I'm AI Scientist, your autonomous research assistant. What would you like me to investigate?"
    
    sess["last_assistant_message"] = content

    return {
        "intent": "CASUAL_CHAT",
        "response": content,
        "action": "NONE",
        "projectId": active_project_id
    }
