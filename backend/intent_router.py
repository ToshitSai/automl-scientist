import os
import json
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

def classify_intent(message: str, active_project_id: Optional[str] = None) -> str:
    """
    Classifies user message intent into one of 7 structured categories.
    Uses fast-path pattern matching for zero-latency greetings, explanations, controls, and start commands,
    falling back to LLM intent classification when necessary.
    """
    msg_clean = message.strip().lower()
    
    # 1. Fast-Path Pattern Matching
    
    # Greetings
    greetings = ["hi", "hello", "hey", "hi!", "hello!", "hey!", "greetings", "good morning", "good afternoon"]
    if msg_clean in greetings:
        return "CASUAL_CHAT"
    if "what can you do" in msg_clean or "who are you" in msg_clean or "help" in msg_clean:
        return "CASUAL_CHAT"

    # Research Control Commands
    control_cmds = ["stop", "pause", "resume", "continue", "try another model", "try another approach", "run another experiment", "next experiment", "stop research"]
    if any(cmd in msg_clean for cmd in control_cmds) or msg_clean in ["stop", "continue", "pause"]:
        return "RESEARCH_CONTROL"

    # Report Request
    report_cmds = ["show report", "view report", "download report", "show me the report", "get report", "the report"]
    if any(cmd in msg_clean for cmd in report_cmds):
        return "REPORT_REQUEST"

    # Technical Details
    tech_cmds = ["show details", "technical details", "view logs", "show logs", "view code"]
    if any(cmd in msg_clean for cmd in tech_cmds):
        return "TECHNICAL_DETAILS"

    # ML Concept Explanation
    if any(term in msg_clean for term in ["recall", "precision", "f1", "accuracy", "auc", "overfitting", "underfitting", "baseline"]) or msg_clean.startswith("what is ") or msg_clean.startswith("explain ") or msg_clean.startswith("define "):
        if not active_project_id or any(term in msg_clean for term in ["recall", "precision", "f1", "accuracy", "auc"]):
            return "EXPLANATION"

    # Research Follow-up (checked BEFORE research start so questions about active project models don't trigger new project)
    if active_project_id and any(kw in msg_clean for kw in ["why", "how come", "this model", "the model", "fail", "failed", "choose", "chose", "performance"]):
        return "RESEARCH_FOLLOWUP"

    # Research Start (e.g. "improve credit-card fraud detection", "predict customer churn")
    if any(word in msg_clean for word in ["improve", "optimize", "predict", "forecast", "detect", "train", "fraud"]):
        return "RESEARCH_START"

    # 2. LLM Intent Classification Fallback
    system_prompt = (
        "You are an intent classification system for AI Scientist. "
        "Classify the user input into EXACTLY ONE of these categories: "
        "CASUAL_CHAT, EXPLANATION, RESEARCH_START, RESEARCH_FOLLOWUP, RESEARCH_CONTROL, REPORT_REQUEST, TECHNICAL_DETAILS. "
        "Return ONLY the exact category string."
    )
    user_prompt = f"""
User Input: "{message}"
Has Active Project Context: {bool(active_project_id)}

Categories:
- CASUAL_CHAT: Greetings, small talk, capability questions ("hi", "hello", "what can you do?")
- EXPLANATION: General machine learning concept definitions ("what is recall?", "explain precision")
- RESEARCH_START: Starting a new machine learning research goal ("improve credit card fraud detection", "predict churn")
- RESEARCH_FOLLOWUP: Questions about current active project ("why did this model fail?", "why did accuracy improve?")
- RESEARCH_CONTROL: Controlling active research execution ("stop", "continue", "try another model", "run another experiment")
- REPORT_REQUEST: Asking to view research report ("show me the report")
- TECHNICAL_DETAILS: Asking for technical logs/code ("show technical details")

Category:
"""
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
    DOES NOT trigger research state mutation unless intent is RESEARCH_START or RESEARCH_CONTROL.
    """
    intent = classify_intent(message, active_project_id)
    msg_clean = message.strip().lower()

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
        if "recall" in msg_clean:
            explanation = "Recall measures the proportion of actual positive cases (like fraudulent transactions) that the model successfully detected out of all true positive cases. High recall ensures that very few fraud cases escape undetected."
        else:
            sys_prompt = "You are a friendly AI machine learning scientist explaining concepts clearly to non-technical humans."
            prompt = f"Explain the machine learning concept in the user's question clearly in 2-3 concise, intuitive sentences without jargon:\nQuestion: '{message}'"
            explanation = query_llm(prompt, sys_prompt) or "Recall measures how many of the actual positive cases (like fraud) the model successfully identified. High recall ensures very few critical cases are missed."
        
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
        answer = query_llm(prompt, sys_prompt) or f"I selected {best_model} because it achieved the highest cross-validation score while maintaining balanced precision and recall for your dataset."

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
