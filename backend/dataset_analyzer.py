import os
import csv
from typing import Dict, Any, List

def analyze_dataset(file_path: str) -> Dict[str, Any]:
    """
    Performs real statistical analysis on a CSV or Parquet dataset file.
    Supports both pandas/numpy and standard library fallback when pandas is unavailable.
    Does NOT use fake/hardcoded values.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found at {file_path}")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    file_size_str = f"{file_size_mb:.2f} MB"

    try:
        import pandas as pd
        import numpy as np
        return _analyze_with_pandas(file_path, file_size_str)
    except ImportError:
        return _analyze_with_stdlib(file_path, file_size_str)

def _analyze_with_pandas(file_path: str, file_size_str: str) -> Dict[str, Any]:
    import pandas as pd
    import numpy as np

    if file_path.endswith(".parquet"):
        df = pd.read_parquet(file_path)
    else:
        df = pd.read_csv(file_path)

    row_count = int(len(df))
    col_count = int(df.shape[1])

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category', 'string']).columns.tolist()
    dt_cols = df.select_dtypes(include=['datetime', 'datetime64']).columns.tolist()

    missing_total = int(df.isnull().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    target_col = None
    lower_cols = [c.lower() for c in df.columns]
    for candidate in ['target', 'class', 'label', 'churn', 'fraud', 'is_fraud', 'outcome', 'price']:
        if candidate in lower_cols:
            target_col = df.columns[lower_cols.index(candidate)]
            break

    if target_col is None:
        target_col = df.columns[-1]

    task_type = "classification"
    class_distribution = []

    unique_vals = df[target_col].nunique(dropna=True)
    if unique_vals <= 20 and (df[target_col].dtype == 'object' or pd.api.types.is_integer_dtype(df[target_col])):
        task_type = "classification"
        val_counts = df[target_col].value_counts(normalize=False, dropna=True)
        val_pcts = df[target_col].value_counts(normalize=True, dropna=True)

        for val, count in val_counts.items():
            pct = round(float(val_pcts[val]) * 100, 2)
            class_distribution.append({
                "label": f"{val}",
                "count": int(count),
                "percentage": pct
            })
    else:
        task_type = "regression"
        target_series = pd.to_numeric(df[target_col], errors='coerce').dropna()
        class_distribution.append({
            "label": "Regression Target (Continuous)",
            "count": int(len(target_series)),
            "percentage": 100.0,
            "mean": float(target_series.mean()) if len(target_series) > 0 else 0,
            "min": float(target_series.min()) if len(target_series) > 0 else 0,
            "max": float(target_series.max()) if len(target_series) > 0 else 0
        })

    detected_issues = []
    if task_type == "classification" and len(class_distribution) >= 2:
        sorted_pcts = sorted([item["percentage"] for item in class_distribution])
        min_pct = sorted_pcts[0]
        if min_pct < 5.0:
            detected_issues.append({
                "severity": "CRITICAL" if min_pct < 1.0 else "MEDIUM",
                "title": "Class Imbalance Detected",
                "desc": f"Minority class accounts for only {min_pct}% of total records. Standard accuracy will be misleading."
            })

    if missing_total > 0:
        missing_pct = round((missing_total / (row_count * col_count)) * 100, 2)
        detected_issues.append({
            "severity": "MEDIUM" if missing_pct > 5 else "LOW",
            "title": "Missing Values Present",
            "desc": f"Found {missing_total} missing values ({missing_pct}% of total cells) across dataset."
        })

    if duplicate_rows > 0:
        detected_issues.append({
            "severity": "LOW",
            "title": "Duplicate Rows",
            "desc": f"{duplicate_rows} exact duplicate feature rows detected. Deduplication recommended."
        })

    recommended_metrics = _get_recommended_metrics(task_type, detected_issues)

    return {
        "filename": os.path.basename(file_path),
        "rowCount": row_count,
        "columnCount": col_count,
        "fileSize": file_size_str,
        "targetCandidate": target_col,
        "taskType": task_type,
        "classDistribution": class_distribution,
        "missingValuesTotal": missing_total,
        "duplicateRows": duplicate_rows,
        "numericalColumns": len(num_cols),
        "categoricalColumns": len(cat_cols),
        "datetimeColumns": len(dt_cols),
        "detectedIssues": detected_issues,
        "recommendedMetrics": recommended_metrics
    }

def _analyze_with_stdlib(file_path: str, file_size_str: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty.")

        rows = list(reader)

    row_count = len(rows)
    col_count = len(headers)

    missing_total = 0
    seen_rows = set()
    duplicate_rows = 0

    col_values = {h: [] for h in headers}

    for row in rows:
        row_tuple = tuple(row)
        if row_tuple in seen_rows:
            duplicate_rows += 1
        else:
            seen_rows.add(row_tuple)

        for i, val in enumerate(row):
            if i < len(headers):
                val_str = val.strip()
                if not val_str:
                    missing_total += 1
                else:
                    col_values[headers[i]].append(val_str)

    target_col = None
    lower_cols = [h.lower() for h in headers]
    for candidate in ['target', 'class', 'label', 'churn', 'fraud', 'is_fraud', 'outcome', 'price']:
        if candidate in lower_cols:
            target_col = headers[lower_cols.index(candidate)]
            break

    if target_col is None:
        target_col = headers[-1]

    # Analyze target column
    target_vals = col_values.get(target_col, [])
    unique_target_vals = set(target_vals)

    task_type = "classification"
    class_distribution = []

    if len(unique_target_vals) <= 20:
        task_type = "classification"
        counts = {}
        for v in target_vals:
            counts[v] = counts.get(v, 0) + 1

        total_t = len(target_vals) or 1
        for val, count in counts.items():
            pct = round((count / total_t) * 100, 2)
            class_distribution.append({
                "label": str(val),
                "count": count,
                "percentage": pct
            })
    else:
        task_type = "regression"
        num_target_vals = []
        for v in target_vals:
            try:
                num_target_vals.append(float(v))
            except ValueError:
                pass

        mean_v = sum(num_target_vals) / len(num_target_vals) if num_target_vals else 0.0
        min_v = min(num_target_vals) if num_target_vals else 0.0
        max_v = max(num_target_vals) if num_target_vals else 0.0

        class_distribution.append({
            "label": "Regression Target (Continuous)",
            "count": len(num_target_vals),
            "percentage": 100.0,
            "mean": round(mean_v, 2),
            "min": round(min_v, 2),
            "max": round(max_v, 2)
        })

    num_cols_cnt = 0
    cat_cols_cnt = 0
    for h in headers:
        vals = col_values.get(h, [])[:50]
        is_num = True
        for v in vals:
            try:
                float(v)
            except ValueError:
                is_num = False
                break
        if is_num and len(vals) > 0:
            num_cols_cnt += 1
        else:
            cat_cols_cnt += 1

    detected_issues = []
    if task_type == "classification" and len(class_distribution) >= 2:
        sorted_pcts = sorted([item["percentage"] for item in class_distribution])
        min_pct = sorted_pcts[0]
        if min_pct < 5.0:
            detected_issues.append({
                "severity": "CRITICAL" if min_pct < 1.0 else "MEDIUM",
                "title": "Class Imbalance Detected",
                "desc": f"Minority class accounts for only {min_pct}% of total records. Standard accuracy will be misleading."
            })

    if missing_total > 0:
        missing_pct = round((missing_total / (row_count * col_count if row_count * col_count > 0 else 1)) * 100, 2)
        detected_issues.append({
            "severity": "MEDIUM" if missing_pct > 5 else "LOW",
            "title": "Missing Values Present",
            "desc": f"Found {missing_total} missing values ({missing_pct}% of total cells) across dataset."
        })

    if duplicate_rows > 0:
        detected_issues.append({
            "severity": "LOW",
            "title": "Duplicate Rows",
            "desc": f"{duplicate_rows} exact duplicate feature rows detected. Deduplication recommended."
        })

    recommended_metrics = _get_recommended_metrics(task_type, detected_issues)

    return {
        "filename": os.path.basename(file_path),
        "rowCount": row_count,
        "columnCount": col_count,
        "fileSize": file_size_str,
        "targetCandidate": target_col,
        "taskType": task_type,
        "classDistribution": class_distribution,
        "missingValuesTotal": missing_total,
        "duplicateRows": duplicate_rows,
        "numericalColumns": num_cols_cnt,
        "categoricalColumns": cat_cols_cnt,
        "datetimeColumns": 0,
        "detectedIssues": detected_issues,
        "recommendedMetrics": recommended_metrics
    }

def _get_recommended_metrics(task_type: str, detected_issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if task_type == "classification":
        if any(issue["title"] == "Class Imbalance Detected" for issue in detected_issues):
            return [
                {"name": "PR-AUC (Precision-Recall Area)", "importance": "Primary", "reason": "Evaluates minority class predictions without true-negative bias."},
                {"name": "F1-Score", "importance": "Secondary", "reason": "Harmonic mean of precision and recall for balanced evaluation."},
                {"name": "Recall", "importance": "Benchmark", "reason": "Measures percentage of positive targets successfully captured."},
                {"name": "ROC-AUC", "importance": "Contextual", "reason": "Standard ranking discrimination benchmark."}
            ]
        else:
            return [
                {"name": "F1-Score", "importance": "Primary", "reason": "Balanced metric for standard multi-class / binary classification."},
                {"name": "Accuracy", "importance": "Benchmark", "reason": "Overall fraction of correct predictions."},
                {"name": "ROC-AUC", "importance": "Secondary", "reason": "Measures class separation capability."}
            ]
    else:
        return [
            {"name": "R2 Score (Coefficient of Determination)", "importance": "Primary", "reason": "Proportion of variance explained by model."},
            {"name": "RMSE (Root Mean Squared Error)", "importance": "Secondary", "reason": "Penalizes larger forecast errors in same units as target."},
            {"name": "MAE (Mean Absolute Error)", "importance": "Benchmark", "reason": "Interpretable average magnitude of absolute errors."}
        ]
