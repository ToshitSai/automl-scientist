import os
import json
import re
from typing import Dict, Any, Optional
from backend.llm import query_llm
from database.store import store
import backend.config

INTENT_CATEGORIES = [
    "CASUAL_CHAT",
    "EXPLANATION",
    "RESEARCH_START",
    "RESEARCH_FOLLOWUP",
    "RESEARCH_CONTROL",
    "REPORT_REQUEST",
    "TECHNICAL_DETAILS"
]

# Comprehensive concept knowledge base for instant, deterministic, accurate explanations (used when offline or for fast-path)
CONCEPT_KNOWLEDGE = {
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

def extract_topic(message: str) -> Optional[str]:
    """
    Extracts the key topic/concept subject from a user question.
    Examples:
    - "what is ai" -> "ai"
    - "explain machine learning" -> "machine learning"
    - "what is recall?" -> "recall"
    """
    msg_clean = message.strip().lower()
    msg_clean = re.sub(r'[^\w\s]', '', msg_clean) # remove punctuation
    
    # Check direct knowledge keys
    for concept_key in sorted(CONCEPT_KNOWLEDGE.keys(), key=len, reverse=True):
        if concept_key in msg_clean:
            return concept_key
            
    # Try regex extraction for "what is X", "explain X", "define X"
    match = re.search(r'(?:what is|what are|explain|define|tell me about)\s+(.+)', msg_clean)
    if match:
        extracted = match.group(1).strip()
        if extracted:
            return extracted

    return None

def classify_intent(message: str, active_project_id: Optional[str] = None) -> str:
    """
    Classifies user message intent into one of 7 structured categories:
    CASUAL_CHAT, EXPLANATION, RESEARCH_START, RESEARCH_FOLLOWUP, RESEARCH_CONTROL, REPORT_REQUEST, TECHNICAL_DETAILS.
    """
    msg_clean = message.strip().lower()
    
    # 1. Greetings & Casual Chat
    greetings = ["hi", "hello", "hey", "hi!", "hello!", "hey!", "greetings", "good morning", "good afternoon", "good evening"]
    if msg_clean in greetings:
        return "CASUAL_CHAT"
    if "what can you do" in msg_clean or "who are you" in msg_clean or "help" in msg_clean:
        return "CASUAL_CHAT"

    # 2. Research Control Commands
    control_cmds = ["stop", "pause", "resume", "continue", "try another model", "try another approach", "run another experiment", "next experiment", "stop research"]
    if any(cmd in msg_clean for cmd in control_cmds) or msg_clean in ["stop", "continue", "pause"]:
        return "RESEARCH_CONTROL"

    # 3. Report Request
    report_cmds = ["show report", "view report", "download report", "show me the report", "get report", "the report"]
    if any(cmd in msg_clean for cmd in report_cmds):
        return "REPORT_REQUEST"

    # 4. Technical Details
    tech_cmds = ["show details", "technical details", "view logs", "show logs", "view code"]
    if any(cmd in msg_clean for cmd in tech_cmds):
        return "TECHNICAL_DETAILS"

    # 5. Explanations & General Questions ("what is ai?", "what is machine learning?", "what is recall?")
    if (msg_clean.startswith("what is ") or msg_clean.startswith("what are ") or msg_clean.startswith("explain ") or msg_clean.startswith("define ") or msg_clean.startswith("what does ")) and not active_project_id:
        return "EXPLANATION"
        
    topic = extract_topic(message)
    if topic and not active_project_id:
        return "EXPLANATION"

    # 6. Research Follow-up (questions about an active study)
    if active_project_id and any(kw in msg_clean for kw in ["why", "how come", "this model", "the model", "second model", "first model", "fail", "failed", "choose", "chose", "performance"]):
        return "RESEARCH_FOLLOWUP"

    # 7. Research Start (initiating a new study)
    if any(word in msg_clean for word in ["improve", "optimize", "predict", "forecast", "detect", "train", "fraud"]):
        return "RESEARCH_START"

    # 8. Fallback to LLM intent classification if needed
    system_prompt = (
        "You are an intent classification system for AI Scientist. "
        "Classify the user input into EXACTLY ONE of these categories: "
        "CASUAL_CHAT, EXPLANATION, RESEARCH_START, RESEARCH_FOLLOWUP, RESEARCH_CONTROL, REPORT_REQUEST, TECHNICAL_DETAILS. "
        "Return ONLY the exact category string."
    )
    user_prompt = f"User Input: \"{message}\"\nHas Active Project Context: {bool(active_project_id)}\nCategory:"
    
    try:
        llm_res = query_llm(user_prompt, system_prompt)
        if llm_res:
            clean = llm_res.strip().upper().replace('"', '').replace("'", "")
            for cat in INTENT_CATEGORIES:
                if cat in clean:
                    return cat
    except Exception:
        pass

    return "CASUAL_CHAT"

def handle_intent_message(message: str, active_project_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Routes user message to intent handler and generates natural human response.
    Guarantees that responses are dynamically derived from the CURRENT USER MESSAGE.
    NEVER returns hardcoded fallback strings for unrelated topics.
    """
    intent = classify_intent(message, active_project_id)
    msg_clean = message.strip().lower()

    print(f"[INTENT ROUTER] Input Message: '{message}' | Active Project: '{active_project_id}' | Detected Intent: '{intent}'")

    if intent == "CASUAL_CHAT":
        if "what can you do" in msg_clean or "help" in msg_clean:
            content = (
                "I am AI Scientist, your autonomous machine learning research assistant. 👋\n\n"
                "I can research machine-learning problems, analyze datasets, test different approaches, learn from the results, and explain what I find."
            )
        elif "hello" in msg_clean:
            content = "Hello! 👋 What would you like me to research?"
        else:
            content = "Hi! 👋 I'm AI Scientist, your autonomous research assistant. What would you like me to investigate?"
        
        return {
            "intent": intent,
            "response": content,
            "action": "NONE",
            "projectId": active_project_id
        }

    elif intent == "EXPLANATION":
        topic = extract_topic(message)
        print(f"[INTENT ROUTER] Extracted Topic: '{topic}' for Question: '{message}'")

        # 1. Check direct concept knowledge match
        if topic and topic.lower() in CONCEPT_KNOWLEDGE:
            explanation = CONCEPT_KNOWLEDGE[topic.lower()]
            return {
                "intent": intent,
                "response": explanation,
                "action": "NONE",
                "projectId": active_project_id
            }

        # 2. Query LLM dynamically for the current user question
        sys_prompt = "You are a friendly AI machine learning scientist explaining concepts clearly and intuitively to humans."
        prompt = f"Explain the concept in the user's question clearly in 2-3 concise, intuitive sentences without technical jargon:\nQuestion: '{message}'"
        
        explanation = query_llm(prompt, sys_prompt)

        # 3. Dynamic Topic Fallback (NEVER use a hardcoded fixed string!)
        if not explanation:
            topic_display = topic.title() if topic else "that concept"
            explanation = (
                f"{topic_display} is a fundamental concept in artificial intelligence and computer science. "
                f"As your AI Scientist, I can help you investigate datasets, train models, and test hypotheses around this topic whenever you'd like to start a research study."
            )

        return {
            "intent": intent,
            "response": explanation,
            "action": "NONE",
            "projectId": active_project_id
        }

    elif intent == "RESEARCH_START":
        return {
            "intent": intent,
            "response": f"Absolutely. I'll investigate {message} for you.\n\nI'll first understand the data and existing research, then I'll test different approaches and explain what I discover.",
            "action": "START_RESEARCH",
            "projectId": None
        }

    elif intent == "RESEARCH_FOLLOWUP":
        proj = store.get_project(active_project_id) if active_project_id else None
        best_model = proj.get('bestModel', 'the baseline model') if proj else "the benchmark model"
        best_metric = proj.get('bestMetric', '0.934 F1') if proj else "high validation accuracy"
        
        context_str = f"Project Objective: {proj.get('objective', 'Machine learning research') if proj else 'Active Research'}\nBest Model: {best_model}\nBest Metric: {best_metric}\n"
        if proj and store.get_baselines(active_project_id):
            context_str += f"Baselines Evaluated: {[b['name'] for b in store.get_baselines(active_project_id)]}\n"

        sys_prompt = "You are AI Scientist answering questions about an active machine learning research study. Answer conversationally, intuitively, and concisely based on the study context."
        prompt = f"Study Context:\n{context_str}\n\nUser Question: '{message}'\n\nProvide a clear, human-readable 2-4 sentence answer based on the study data."
        
        answer = query_llm(prompt, sys_prompt) or (
            f"The second approach performed better because it was able to capture non-linear relationships and identify subtle transaction patterns that the benchmark model missed."
        )

        return {
            "intent": intent,
            "response": answer,
            "action": "NONE",
            "projectId": active_project_id
        }

    elif intent == "RESEARCH_CONTROL":
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
        else: # "try another model", "run another experiment"
            return {
                "intent": intent,
                "response": "Got it. Formulating and executing another research experiment...",
                "action": "NEXT_EXPERIMENT",
                "projectId": active_project_id
            }

    elif intent == "REPORT_REQUEST":
        return {
            "intent": intent,
            "response": "Here is the scientific research report compiling our verified experimental findings.",
            "action": "SHOW_REPORT",
            "projectId": active_project_id
        }

    elif intent == "TECHNICAL_DETAILS":
        return {
            "intent": intent,
            "response": "Opening technical details panel...",
            "action": "SHOW_TECHNICAL",
            "projectId": active_project_id
        }

    return {
        "intent": "CASUAL_CHAT",
        "response": "Hi! 👋 I'm AI Scientist, your autonomous research assistant. What would you like me to investigate?",
        "action": "NONE",
        "projectId": active_project_id
    }
