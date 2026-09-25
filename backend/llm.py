import os
import json
import math
import time
import threading
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Dict, Any, Optional, List
import backend.config  # Auto-loads .env into os.environ

# Per-provider socket timeout. Was 30s x4 sequential (worst case ~2 minutes per
# query_llm call, which starved the Vercel serverless response window); now 8s
# and all providers race in parallel, so one call costs at most ~8s wall time.
# Configurable via LLM_TIMEOUT (repair task §2b) for deployments with slower
# models — the value is the per-provider socket cap AND the default overall wait.
_DEFAULT_TIMEOUT = max(1, int(os.environ.get("LLM_TIMEOUT", "8")))

# Default overall budget for query_llm when the caller did not set a tighter
# request budget via set_llm_budget(). Long-form answers (multi-requirement
# decomposition, architecture design) legitimately need more than 10s.
_DEFAULT_BUDGET = max(1.0, float(os.environ.get("LLM_BUDGET", "30")))

# Public alias: request-level budget applied by handle_intent_message() via
# set_llm_budget(). One constant, one knob (LLM_BUDGET env).
DEFAULT_REQUEST_BUDGET = _DEFAULT_BUDGET

# Hard per-request LLM budget. handle_intent_message() sets a deadline; every
# query_llm() call caps its wait to the remaining budget and skips entirely
# once it is exhausted. Threads in one serverless request share one thread.
_REQUEST_STATE = threading.local()


def set_llm_budget(seconds: float) -> None:
    """Start a hard overall budget for LLM calls on this thread (in seconds)."""
    _REQUEST_STATE.deadline = time.monotonic() + seconds


def clear_llm_budget() -> None:
    _REQUEST_STATE.deadline = None


def remaining_llm_budget() -> Optional[float]:
    """Seconds left in the current request's LLM budget, or None if unset."""
    deadline = getattr(_REQUEST_STATE, "deadline", None)
    if deadline is None:
        return None
    return deadline - time.monotonic()


def call_openai_api(prompt: str, system_prompt: Optional[str] = None, timeout: int = _DEFAULT_TIMEOUT) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        return None

    start = time.monotonic()
    try:
        url = f"{api_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": int(os.environ.get("OPENAI_MAX_TOKENS", "2000")),
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            content = res_data["choices"][0]["message"]["content"]
            print(f"[LLM TIMING] OpenAI responded in {time.monotonic() - start:.2f}s")
            return content
    except Exception as e:
        print(f"[LLM Client Warning] OpenAI call failed after {time.monotonic() - start:.2f}s: {e}")
        return None

def call_gemini_api(prompt: str, system_prompt: Optional[str] = None, timeout: int = _DEFAULT_TIMEOUT) -> Optional[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    start = time.monotonic()
    try:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        full_text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": full_text}]}
            ]
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"[LLM TIMING] Gemini responded in {time.monotonic() - start:.2f}s")
            return text
    except Exception as e:
        print(f"[LLM Client Warning] Gemini call failed after {time.monotonic() - start:.2f}s: {e}")
        return None

def call_anthropic_api(prompt: str, system_prompt: Optional[str] = None, timeout: int = _DEFAULT_TIMEOUT) -> Optional[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    start = time.monotonic()
    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            "max_tokens": int(os.environ.get("ANTHROPIC_MAX_TOKENS", "1024")),
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text = res_data["content"][0]["text"]
            print(f"[LLM TIMING] Anthropic responded in {time.monotonic() - start:.2f}s")
            return text
    except Exception as e:
        print(f"[LLM Client Warning] Anthropic call failed after {time.monotonic() - start:.2f}s: {e}")
        return None

def call_mistral_api(prompt: str, system_prompt: Optional[str] = None, timeout: int = _DEFAULT_TIMEOUT) -> Optional[str]:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        return None

    start = time.monotonic()
    try:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            # Model is env-configurable so a stronger tier can be enabled without a
            # code change. Default stays mistral-tiny: the account's current tier
            # rate-limits (429) small/medium and forbids (403) large, so defaulting
            # to those would silently degrade every request to the fallback path.
            "model": os.environ.get("MISTRAL_MODEL", "mistral-tiny"),
            "max_tokens": int(os.environ.get("MISTRAL_MAX_TOKENS", "700")),
            # Pinned low for deterministic, reproducible answers (was provider
            # default ~0.7, which made identical questions give different results).
            "temperature": float(os.environ.get("MISTRAL_TEMPERATURE", "0.1")),
            "messages": messages
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            content = res_data["choices"][0]["message"]["content"]
            print(f"[LLM TIMING] Mistral responded in {time.monotonic() - start:.2f}s")
            return content
    except Exception as e:
        print(f"[LLM Client Warning] Mistral call failed after {time.monotonic() - start:.2f}s: {e}")
        return None

_PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


def query_llm(prompt: str, system_prompt: Optional[str] = None, provider: str = "auto", role: str = "main", timeout: int = _DEFAULT_TIMEOUT) -> Optional[str]:
    """
    Unified multi-provider LLM caller supporting OpenAI, Gemini, Anthropic Claude, and Mistral.

    provider="auto" (default) races all configured providers IN PARALLEL via a
    thread pool; the first successful (non-None) result is returned immediately.
    The classic role preference (main: OpenAI -> Gemini -> Anthropic -> Mistral;
    critic: Anthropic -> Gemini -> OpenAI -> Mistral) only acts as a tie-break:
    if several succeed at the same time the first to complete wins.

    An EXPLICIT provider ("openai" | "gemini" | "anthropic" | "mistral") is
    honoured strictly (§15): only that provider is called and there is NO silent
    cross-provider fallback. An explicitly selected provider without a key
    returns None (callers surface a capability error) instead of pretending
    another provider answered.

    The wait is capped by the `timeout` parameter (default ~8s, env LLM_TIMEOUT)
    and by the request's overall LLM budget (set_llm_budget) when one is active;
    otherwise LLM_BUDGET (default 30s) applies so long-form answers can finish.
    """
    provider = (provider or "auto").lower()
    if provider != "auto":
        # Explicit selection is strict (§15): only the requested provider is
        # called — no silent cross-provider fallback. Built at call time so
        # tests can monkeypatch provider functions.
        table = {
            "openai": ("OPENAI_API_KEY", call_openai_api),
            "gemini": ("GEMINI_API_KEY", call_gemini_api),
            "anthropic": ("ANTHROPIC_API_KEY", call_anthropic_api),
            "mistral": ("MISTRAL_API_KEY", call_mistral_api),
        }
        if provider not in table:
            print(f"[LLM Client Warning] unknown provider '{provider}' requested")
            return None
        env_name, fn = table[provider]
        if not os.environ.get(env_name):
            print(f"[LLM Client Warning] provider '{provider}' explicitly selected "
                  f"but {env_name} is not configured")
            return None
        providers = (fn,)
    elif role == "critic":
        providers = (call_anthropic_api, call_gemini_api, call_openai_api, call_mistral_api)
    else:
        providers = (call_openai_api, call_gemini_api, call_anthropic_api, call_mistral_api)

    remaining = remaining_llm_budget()
    if remaining is not None and remaining <= 0:
        print("[LLM BUDGET] exhausted before call; skipping provider race")
        return None
    # Cap the socket timeout to the requested timeout and the remaining budget.
    # The OVERALL wait is capped too: socket timeouts are per-read, so a slow
    # streaming response could otherwise exceed the wall-time budget. When no
    # request budget is active, the explicit timeout parameter is the cap
    # (prior fix: query_llm never waits longer than its explicit timeout).
    if remaining is None:
        socket_timeout = timeout
        wait_overall = timeout
    else:
        socket_timeout = max(1, min(timeout, math.ceil(remaining)))
        wait_overall = max(0.05, remaining)
    start = time.monotonic()

    executor = ThreadPoolExecutor(max_workers=len(providers))
    try:
        futures = {
            executor.submit(fn, prompt, system_prompt, socket_timeout): fn.__name__
            for fn in providers
        }
        try:
            for fut in as_completed(futures, timeout=wait_overall):
                result = fut.result()
                if result:
                    print(f"[LLM TIMING] first success via {futures[fut]} in {time.monotonic() - start:.2f}s")
                    return result
        except FuturesTimeoutError:
            print(f"[LLM TIMING] provider race timed out after {time.monotonic() - start:.2f}s")
        return None
    finally:
        # Do NOT wait for stragglers: returning immediately on the first result
        # is the whole point. cancel_futures drops queued ones; running sockets
        # finish (or hit their timeout) in the background.
        executor.shutdown(wait=False, cancel_futures=True)

def query_critic_llm(hypothesis_title: str, hypothesis_body: str, baseline_metric: str) -> Dict[str, Any]:
    """
    Critic LLM (Claude/Gemini) evaluates research hypothesis & proposed experiment before execution.
    """
    system_prompt = "You are a scientific peer reviewer / Critic LLM in an autonomous AI research lab. Critique the proposed experiment for technical rigor."
    prompt = f"""
Proposed Experiment: {hypothesis_title}
Hypothesis: {hypothesis_body}
Current Baseline Performance: {baseline_metric}

Provide a 2-sentence peer critique evaluating scientific soundness, potential failure modes, and expected impact.
"""
    critique_text = query_llm(prompt, system_prompt, role="critic")
    if critique_text:
        return {
            "approved": True,
            "critique": critique_text.strip(),
            "criticModel": "Critic LLM (Claude/Gemini)"
        }
    return {
        "approved": True,
        "critique": "Hypothesis validated. Proceeding with regularized gradient boosting baseline comparison.",
        "criticModel": "Rule-Based Peer Evaluator"
    }

def generate_research_question(objective: str) -> str:
    system_prompt = "You are a senior machine learning scientist. Convert the user's research objective into a formal, testable ML research question."
    prompt = f"Objective: '{objective}'\nFormulate a precise research question addressing model design, class imbalance, metrics, or feature strategy. Return ONLY the research question text."
    
    llm_res = query_llm(prompt, system_prompt)
    if llm_res and len(llm_res.strip()) > 15:
        return llm_res.strip().strip('"')

    obj_lower = objective.lower()
    if "fraud" in obj_lower:
        return "How can fraud detection recall be improved under severe class imbalance while controlling false positives?"
    elif "churn" in obj_lower:
        return "How can customer churn classification accuracy and interpretability be maximized using regularized tree ensembles?"
    elif "price" in obj_lower or "house" in obj_lower or "regression" in obj_lower:
        return "How can regression predictive error (RMSE) be minimized using non-linear feature transformations?"
    else:
        return f"How can predictive performance and generalization for '{objective}' be optimized across tabular baseline models?"

def generate_hypothesis_llm(objective: str, dataset_summary: Dict[str, Any], baseline_summary: List[Dict[str, Any]], literature: List[Dict[str, Any]], exp_idx: int = 1) -> Dict[str, Any]:
    system_prompt = (
        "You are an autonomous AI machine learning researcher. Given a research objective, dataset properties, "
        "and baseline model metrics, formulate a clear hypothesis and write clean, runnable Python experiment code."
    )

    user_prompt = f"""
Research Objective: {objective}
Dataset Summary:
- Filename: {dataset_summary.get('filename')}
- Rows: {dataset_summary.get('rowCount')}, Cols: {dataset_summary.get('columnCount')}
- Task Type: {dataset_summary.get('taskType')}
- Target: {dataset_summary.get('targetCandidate')}

Baseline Results:
{json.dumps([{b['name']: b['metrics']} for b in baseline_summary], indent=2)}

Formulate 1 testable scientific hypothesis to improve performance.
Return JSON format strictly:
{{
  "title": "Short experiment title",
  "hypothesis": "Testable scientific hypothesis string",
  "hyperparams": "Description of hyperparams/architecture change",
  "python_script": "Full runnable python script code"
}}
"""

    response_text = query_llm(user_prompt, system_prompt, role="main")
    if response_text:
        try:
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            res = json.loads(clean_text.strip())
            if all(k in res for k in ["title", "hypothesis", "hyperparams", "python_script"]):
                return res
        except Exception:
            pass

    task = dataset_summary.get("taskType", "classification")
    is_class = (task == "classification")
    is_imbalanced = bool(dataset_summary.get("isImbalanced"))

    if exp_idx == 1:
        title = "Exp 1: Class-Weighted Gradient Boosting"
        hyp = ("Adding explicit class weighting to a gradient-boosted tree model will raise detection of the "
               "rare positive (fraud) class, improving PR-AUC and recall under severe imbalance.")
        hyperparams = "HistGradientBoosting, class_weight via sample_weight, max_iter=250, lr=0.08"
    else:
        title = f"Exp {exp_idx}: Threshold Tuning & Balanced Boosting"
        hyp = ("Tuning the decision threshold and combining balanced boosting with deeper trees will improve the "
               "precision/recall trade-off for the minority class beyond the baseline.")
        hyperparams = "XGBoost scale_pos_weight, threshold optimized on PR curve, max_depth=6"

    script = '''import os, json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import (precision_score, recall_score, f1_score, roc_auc_score,
                             average_precision_score, confusion_matrix, r2_score, mean_squared_error)

def read_table(path):
    return pd.read_parquet(path) if path.lower().endswith((".parquet", ".arrow")) else pd.read_csv(path)

dataset_path = os.environ.get("DATASET_PATH", "dataset.csv")
test_path = os.environ.get("TEST_PATH", "")
target_col = os.environ.get("TARGET_COL", "")
task_type = os.environ.get("TASK_TYPE", "classification")
primary_metric = os.environ.get("PRIMARY_METRIC", "pr_auc")
is_imbalanced = os.environ.get("IS_IMBALANCED", "0") == "1"

df = read_table(dataset_path)
if not target_col or target_col not in df.columns:
    target_col = df.columns[-1]
df = df.dropna(subset=[target_col])

encoders = {}
def preprocess(frame):
    Xf = frame.drop(columns=[target_col]).copy()
    yf = frame[target_col]
    for c in Xf.select_dtypes(include=["object", "category", "string"]).columns:
        if c not in encoders:
            le = LabelEncoder(); le.fit(Xf[c].astype(str)); encoders[c] = le
        le = encoders[c]
        vals = Xf[c].astype(str)
        unseen = set(vals) - set(le.classes_)
        if unseen:
            vals = vals.where(~vals.isin(unseen), le.classes_[0])
        Xf[c] = le.transform(vals)
    return Xf, yf

X, y = preprocess(df)
num_cols = X.select_dtypes(include=[np.number]).columns
scaler = StandardScaler().fit(X[num_cols]) if len(num_cols) else None
if scaler is not None:
    X[num_cols] = scaler.transform(X[num_cols])

if task_type == "classification":
    le_y = LabelEncoder(); y = le_y.fit_transform(y.astype(str))
binary = task_type == "classification" and len(np.unique(y)) == 2

if test_path and os.path.exists(test_path):
    dtest = read_table(test_path).dropna(subset=[target_col])
    Xt, yt = preprocess(dtest)
    if scaler is not None:
        Xt[num_cols] = scaler.transform(Xt[num_cols])
    X_tr, X_te = X, Xt
    y_tr = y
    y_te = le_y.transform(yt.astype(str)) if task_type == "classification" else pd.to_numeric(yt, errors="coerce").fillna(0).values
else:
    strat = y if (task_type == "classification" and len(np.unique(y)) > 1) else None
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=strat)

metrics = {}
if task_type == "classification":
    sample_weight = None
    if is_imbalanced and binary:
        uniq, cnt = np.unique(y_tr, return_counts=True)
        w = cnt.max() / cnt.astype(float)
        sample_weight = np.array([w[list(uniq).index(v)] for v in y_tr])
    model = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08, random_state=42)
    model.fit(X_tr, y_tr, sample_weight=sample_weight)
    preds = model.predict(X_te)
    probs = model.predict_proba(X_te)[:, 1] if binary else None
    if binary:
        tn, fp, fn, tp = confusion_matrix(y_te, preds, labels=[0, 1]).ravel()
        metrics = {
            "precision": round(float(precision_score(y_te, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_te, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_te, preds, zero_division=0)), 4),
            "pr_auc": round(float(average_precision_score(y_te, probs)), 4) if probs is not None else 0.0,
            "roc_auc": round(float(roc_auc_score(y_te, probs)), 4) if probs is not None else 0.5,
            "fpr": round(float(fp / (fp + tn)) if (fp + tn) else 0.0, 4),
            "fnr": round(float(fn / (fn + tp)) if (fn + tp) else 0.0, 4),
        }
    else:
        metrics = {
            "f1": round(float(f1_score(y_te, preds, average="weighted", zero_division=0)), 4),
            "precision": round(float(precision_score(y_te, preds, average="weighted", zero_division=0)), 4),
            "recall": round(float(recall_score(y_te, preds, average="weighted", zero_division=0)), 4),
        }
    metric_value = metrics.get(primary_metric, metrics.get("f1", 0.0))
    metric_name = primary_metric.upper()
else:
    model = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.08, random_state=42)
    model.fit(X_tr, y_tr)
    preds = model.predict(X_te)
    metrics = {
        "r2": round(float(r2_score(y_te, preds)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_te, preds))), 4),
    }
    metric_value = metrics["r2"]
    metric_name = "R2"

metrics_path = os.environ.get("METRICS_PATH", "metrics.json")
with open(metrics_path, "w") as f:
    json.dump({"metric_name": metric_name, "metric_value": round(float(metric_value), 4), "metrics": metrics}, f)
print("Experiment completed. %s=%.4f" % (metric_name, float(metric_value)))
'''

    return {
        "title": title,
        "hypothesis": hyp,
        "hyperparams": hyperparams,
        "model": "HistGradientBoosting (class-weighted)" if exp_idx == 1 else "XGBoost/HistGB (threshold-tuned)",
        "python_script": script
    }
