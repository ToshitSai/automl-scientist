import os
import json
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional, List

def query_llm(prompt: str, system_prompt: Optional[str] = None, provider: str = "auto") -> Optional[str]:
    """
    Unified LLM API Client for OpenAI / Custom OpenAI-compatible endpoints.
    Falls back gracefully if no API key or endpoint is configured.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        return None

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
            "temperature": 0.2
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[LLM Client Warning] API call failed: {e}")
        return None

def generate_research_question(objective: str) -> str:
    """
    Calls configured LLM to generate a precise machine-learning research question for the objective.
    Falls back to a domain-specific structured research question if LLM is not configured.
    """
    system_prompt = "You are a senior machine learning scientist. Convert the user's research objective into a formal, testable ML research question."
    prompt = f"Objective: '{objective}'\nFormulate a precise research question addressing model design, class imbalance, metrics, or feature strategy. Return ONLY the research question text."
    
    llm_res = query_llm(prompt, system_prompt)
    if llm_res and len(llm_res.strip()) > 15:
        return llm_res.strip().strip('"')

    obj_lower = objective.lower()
    if "fraud" in obj_lower:
        return f"How can fraud detection recall be improved under severe class imbalance while controlling false positives?"
    elif "churn" in obj_lower:
        return f"How can customer churn classification accuracy and interpretability be maximized using regularized tree ensembles?"
    elif "price" in obj_lower or "house" in obj_lower or "regression" in obj_lower:
        return f"How can regression predictive error (RMSE) be minimized using non-linear feature transformations?"
    else:
        return f"How can predictive performance and generalization for '{objective}' be optimized across tabular baseline models?"

def generate_hypothesis_llm(objective: str, dataset_summary: Dict[str, Any], baseline_summary: List[Dict[str, Any]], literature: List[Dict[str, Any]], exp_idx: int = 1) -> Dict[str, Any]:
    """
    Generates a testable hypothesis and Python experiment code using LLM or structured synthesis engine.
    """
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
- Issues: {[i['title'] for i in dataset_summary.get('detectedIssues', [])]}

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

    response_text = query_llm(user_prompt, system_prompt)
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
    
    title = f"Exp {exp_idx}: Regularized Gradient Boosting & Feature Selection" if exp_idx == 1 else f"Exp {exp_idx}: Hyperparameter Optimization & Class Weighting"
    hyp = f"Applying regularized gradient boosted decision trees for {task} will mitigate overfitting and improve validation metrics." if exp_idx == 1 else f"Adjusting decision boundary thresholds and feature scaling for {task} will optimize class recall."
    hyperparams = "n_estimators=150, learning_rate=0.03, max_depth=6" if exp_idx == 1 else "n_estimators=200, learning_rate=0.02, max_depth=4"

    script = f"""import os, json
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.metrics import f1_score, precision_score, recall_score, r2_score, mean_squared_error

dataset_path = os.environ.get("DATASET_PATH", "dataset.csv")
df = pd.read_csv(dataset_path).dropna()
target_col = df.columns[-1]

X = pd.get_dummies(df.drop(columns=[target_col]), drop_first=True)
y = df[target_col]

X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

is_classification = {is_class}
if is_classification:
    model = GradientBoostingClassifier(n_estimators=150, learning_rate=0.03, max_depth=6, random_state=42)
    model.fit(X_tr, y_tr)
    preds = model.predict(X_te)
    f1 = float(f1_score(y_te, preds, average='weighted', zero_division=0))
    prec = float(precision_score(y_te, preds, average='weighted', zero_division=0))
    rec = float(recall_score(y_te, preds, average='weighted', zero_division=0))
    metric_name = "F1-Score"
    score = f1
    extra_metrics = {{"f1": round(f1, 4), "precision": round(prec, 4), "recall": round(rec, 4)}}
else:
    model = GradientBoostingRegressor(n_estimators=150, learning_rate=0.03, max_depth=6, random_state=42)
    model.fit(X_tr, y_tr)
    preds = model.predict(X_te)
    r2 = float(r2_score(y_te, preds))
    mse = float(mean_squared_error(y_te, preds))
    metric_name = "R2-Score"
    score = r2
    extra_metrics = {{"r2": round(r2, 4), "mse": round(mse, 4)}}

metrics_path = os.environ.get("METRICS_PATH", "metrics.json")
with open(metrics_path, "w") as f:
    json.dump({{"metric_name": metric_name, "metric_value": round(score, 4), "metrics": extra_metrics}}, f)
print(f"Experiment completed successfully. Target score: {{score:.4f}}")
"""

    return {
        "title": title,
        "hypothesis": hyp,
        "hyperparams": hyperparams,
        "python_script": script
    }

