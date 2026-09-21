"""
Hugging Face dataset discovery, inspection, and loading.

This module talks to the public Hugging Face Hub API and the raw file resolver
to find, compare, and download REAL datasets. It never fabricates metadata or
data. All numbers reported to the user come from the actual repository.

Note: the project contains a local ``datasets/`` folder, which shadows the
``datasets`` PyPI package when running from the project root. To stay robust we
deliberately avoid ``import datasets`` and instead stream the repository files
(parquet / csv) directly with urllib + pandas/pyarrow.
"""

import os
import io
import re
import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

HF_API = "https://huggingface.co/api/datasets"
HF_WEB = "https://huggingface.co/datasets"
HF_HUB_API = "https://huggingface.co/api/datasets"

_USER_AGENT = "AutoML-Scientist/2.0 (research dataset discovery)"

# Columns that are common fraud / anomaly targets, ordered by preference.
_TARGET_HINTS = [
    "is_fraud", "isfraud", "fraud", "class", "is_fraudulent", "fraudulent",
    "label", "target", "is_anomaly", "anomaly", "default", "default.payment",
    "y", "outcome", "is_default", "is_chargeback", "chargeback", "is_suspicious",
]


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _http_get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_json(url: str, timeout: int = 40) -> Any:
    return json.loads(_http_get(url, timeout=timeout).decode("utf-8", errors="replace"))


# --------------------------------------------------------------------------- #
# URL parsing
# --------------------------------------------------------------------------- #
_HF_URL_RE = re.compile(
    r"https?://huggingface\.co/datasets/([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)",
    re.IGNORECASE,
)


def parse_hf_reference(text: str) -> Dict[str, Any]:
    """
    Classify a user-supplied Hugging Face reference.

    Returns a dict with:
      kind: 'specific'  -> a single dataset repo (owner/name)
            'general'   -> the bare /datasets discovery page
            'none'      -> not a HF reference at all
      repo_id: the owner/name when kind == 'specific'
    """
    if not text:
        return {"kind": "none", "repo_id": None}

    m = _HF_URL_RE.search(text)
    if m:
        repo_id = m.group(1).strip().rstrip("/")
        # Drop trailing segments like /resolve/main or /blob/...
        repo_id = re.split(r"/(resolve|blob|tree|commit|discussions|view)/", repo_id)[0]
        return {"kind": "specific", "repo_id": repo_id}

    lowered = text.strip().lower()
    # Bare discovery page (with or without trailing slash / query params).
    if re.match(r"^https?://huggingface\.co/datasets/?(\?.*)?$", lowered):
        return {"kind": "general", "repo_id": None}

    # A bare "owner/name" token that looks like a repo id.
    bare = re.match(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$", text.strip())
    if bare:
        return {"kind": "specific", "repo_id": text.strip()}

    return {"kind": "none", "repo_id": None}


# --------------------------------------------------------------------------- #
# Tag / metadata helpers
# --------------------------------------------------------------------------- #
def _parse_tags(tags: Optional[List[str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "license": None,
        "size_category": None,
        "format": None,
        "task_categories": [],
        "modality": [],
        "topics": [],
    }
    for t in tags or []:
        if ":" not in t:
            out["topics"].append(t)
            continue
        key, val = t.split(":", 1)
        if key == "license":
            out["license"] = val
        elif key == "size_categories":
            out["size_category"] = val
        elif key == "format":
            out["format"] = val
        elif key == "task_categories":
            out["task_categories"].append(val)
        elif key == "modality":
            out["modality"].append(val)
        elif key == "region":
            continue
        else:
            out["topics"].append(t)
    return out


def _split_files(siblings: Optional[List[Dict[str, Any]]]) -> Dict[str, List[str]]:
    """Map split name -> data file names available in the repository."""
    splits: Dict[str, List[str]] = {"train": [], "test": [], "validation": [], "other": []}
    for sib in siblings or []:
        name = sib.get("rfilename") or ""
        if not name.lower().endswith((".parquet", ".csv", ".arrow", ".json")):
            continue
        low = name.lower()
        base = os.path.basename(low)
        if base.startswith("train") or "/train" in low:
            splits["train"].append(name)
        elif base.startswith("test") or "/test" in low:
            splits["test"].append(name)
        elif base.startswith(("val", "valid", "dev")) or "/val" in low:
            splits["validation"].append(name)
        else:
            splits["other"].append(name)
    return splits


def _resolve_url(repo_id: str, filename: str, revision: str = "main") -> str:
    return f"{HF_WEB}/{repo_id}/resolve/{revision}/{urllib.parse.quote(filename)}"


def _pick_preferred_file(files: List[str]) -> Optional[str]:
    """Prefer combined parquet, then csv, then anything."""
    if not files:
        return None
    for ext in (".parquet", ".csv", ".arrow", ".json"):
        # Prefer files that are NOT feature/label-only splits (X_/y_).
        combined = [f for f in files if f.lower().endswith(ext)
                    and not os.path.basename(f).lower().startswith(("x_", "y_"))]
        if combined:
            return combined[0]
    return files[0]


# --------------------------------------------------------------------------- #
# Public API: search + metadata
# --------------------------------------------------------------------------- #
def search_datasets(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Search the Hugging Face Hub for datasets matching a research goal.

    The Hub search matches phrases fairly literally, so a goal like
    "Improve fraud detection" can return nothing. We therefore try a few
    cleaned query variants (drop action verbs, fall back to key terms) and
    return the first variant that yields real results.
    """
    for variant in _query_variants(query):
        params = urllib.parse.urlencode({
            "search": variant,
            "limit": max(1, min(limit * 3, 30)),
            "full": "true",
            "sort": "downloads",
            "direction": "-1",
        })
        url = f"{HF_API}?{params}"
        try:
            raw = _http_json(url, timeout=40)
        except Exception:
            continue
        if raw:
            candidates = [_summarize_item(it) for it in raw]
            if candidates:
                return candidates[: max(1, limit * 3)]
    return []


_ACTION_VERBS = {
    "improve", "optimize", "optimise", "enhance", "build", "train", "create",
    "make", "increase", "reduce", "maximize", "minimize", "boost", "develop",
    "design", "find", "detect", "predict", "forecast", "better", "using", "use",
}


def _query_variants(goal: str) -> List[str]:
    """Produce progressively cleaner search queries for a research goal."""
    goal = (goal or "").strip()
    if not goal:
        return []
    variants = [goal]

    words = goal.split()
    stripped = [w for w in words if w.lower().strip(".,!?") not in _ACTION_VERBS]
    if stripped and " ".join(stripped).lower() != goal.lower():
        variants.append(" ".join(stripped))

    terms = _goal_terms(goal)
    if terms:
        joined = " ".join(terms)
        if joined not in variants:
            variants.append(joined)

    # De-duplicate while preserving order.
    seen = set()
    out = []
    for v in variants:
        key = v.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _summarize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    parsed = _parse_tags(item.get("tags"))
    card = item.get("cardData") or {}
    desc = item.get("description") or card.get("description") or ""
    return {
        "repoId": item.get("id"),
        "author": item.get("author"),
        "downloads": item.get("downloads", 0),
        "likes": item.get("likes", 0),
        "lastModified": item.get("lastModified"),
        "revision": item.get("sha"),
        "license": parsed["license"] or card.get("license"),
        "sizeCategory": parsed["size_category"],
        "format": parsed["format"],
        "taskCategories": parsed["task_categories"],
        "modality": parsed["modality"],
        "topics": parsed["topics"],
        "gated": bool(item.get("gated")),
        "private": bool(item.get("private")),
        "description": (desc or "")[:400],
    }


def get_dataset_info(repo_id: str) -> Dict[str, Any]:
    """Fetch raw repository metadata for a single dataset."""
    url = f"{HF_API}/{repo_id}"
    return _http_json(url, timeout=40)


# --------------------------------------------------------------------------- #
# Loading real data files
# --------------------------------------------------------------------------- #
def _read_table_bytes(filename: str, data: bytes):
    import pandas as pd
    low = filename.lower()
    if low.endswith(".parquet") or low.endswith(".arrow"):
        return pd.read_parquet(io.BytesIO(data))
    if low.endswith(".json"):
        try:
            return pd.read_json(io.BytesIO(data))
        except Exception:
            return pd.read_json(io.BytesIO(data), lines=True)
    return pd.read_csv(io.BytesIO(data))


def _detect_target(df) -> Optional[str]:
    lower = {c.lower(): c for c in df.columns}
    for hint in _TARGET_HINTS:
        if hint in lower:
            return lower[hint]
    # Fall back to a low-cardinality integer column that looks like a label.
    import numpy as np
    for c in df.columns:
        s = df[c]
        if s.dtype.kind in "ib" and s.nunique(dropna=True) <= 10:
            return c
    return df.columns[-1]


def inspect_dataset(repo_id: str, download_preview: bool = True) -> Dict[str, Any]:
    """
    Return rich, REAL metadata for a dataset, optionally loading the smallest
    available split to read the schema, detect the target, and measure class
    balance. Nothing here is fabricated; if a value cannot be determined it is
    left as None.
    """
    info = get_dataset_info(repo_id)
    parsed = _parse_tags(info.get("tags"))
    card = info.get("cardData") or {}
    splits = _split_files(info.get("siblings"))

    result: Dict[str, Any] = {
        "repoId": info.get("id", repo_id),
        "name": info.get("id", repo_id).split("/")[-1],
        "author": info.get("author"),
        "description": (info.get("description") or card.get("description") or "")[:800],
        "downloads": info.get("downloads", 0),
        "likes": info.get("likes", 0),
        "lastModified": info.get("lastModified"),
        "revision": info.get("sha"),
        "license": parsed["license"] or card.get("license"),
        "sizeCategory": parsed["size_category"],
        "format": parsed["format"],
        "taskCategories": parsed["task_categories"],
        "modality": parsed["modality"],
        "topics": parsed["topics"],
        "gated": bool(info.get("gated")),
        "availableSplits": {k: v for k, v in splits.items() if v},
        "url": f"{HF_WEB}/{repo_id}",
        # Filled in below when a preview file is loaded.
        "featureNames": None,
        "featureCount": None,
        "rowCount": None,
        "targetColumn": None,
        "dtypes": None,
        "classDistribution": None,
        "minorityClassPct": None,
        "previewSplit": None,
        "previewFile": None,
    }

    if not download_preview:
        return result

    # Load the smallest split we can (prefer test/validation, then train, then
    # any loose data files) to read schema + class balance without pulling
    # the whole dataset.
    for split_name in ("test", "validation", "train", "other"):
        fname = _pick_preferred_file(splits.get(split_name, []))
        if not fname:
            continue
        try:
            data = _http_get(_resolve_url(repo_id, fname, info.get("sha") or "main"), timeout=120)
            df = _read_table_bytes(fname, data)
        except Exception as exc:  # noqa: BLE001
            result["previewError"] = f"{split_name}: {exc}"
            continue

        target = _detect_target(df)
        feature_names = [c for c in df.columns if c != target]
        result.update({
            "previewSplit": split_name,
            "previewFile": fname,
            "featureNames": feature_names,
            "featureCount": len(feature_names),
            "rowCount": int(len(df)),
            "targetColumn": target,
            "dtypes": {c: str(t) for c, t in df.dtypes.astype(str).items()},
        })
        if target is not None:
            try:
                vc = df[target].value_counts(dropna=True)
                total = int(vc.sum())
                dist = [{"label": str(k), "count": int(v),
                         "percentage": round(float(v) / total * 100, 3)} for k, v in vc.items()]
                result["classDistribution"] = dist
                if len(dist) > 1:
                    result["minorityClassPct"] = min(d["percentage"] for d in dist)
            except Exception:
                pass
        break

    return result


# --------------------------------------------------------------------------- #
# Download + cache
# --------------------------------------------------------------------------- #
def get_cache_dir() -> str:
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploaded_datasets", "hf_cache")
    os.makedirs(base, exist_ok=True)
    return base


def download_dataset(repo_id: str, dest_dir: Optional[str] = None,
                     max_rows: Optional[int] = None) -> Dict[str, Any]:
    """
    Download the real train/test splits for a dataset into a local folder and
    return their paths. Prefers parquet, falls back to csv. Honors the
    repository's own split boundaries when present.
    """
    import pandas as pd

    info = get_dataset_info(repo_id)
    revision = info.get("sha") or "main"
    splits = _split_files(info.get("siblings"))

    dest_dir = dest_dir or os.path.join(get_cache_dir(), repo_id.replace("/", "__"))
    os.makedirs(dest_dir, exist_ok=True)

    downloaded: Dict[str, str] = {}
    row_counts: Dict[str, int] = {}

    for split_name in ("train", "test", "validation"):
        fname = _pick_preferred_file(splits.get(split_name, []))
        if not fname:
            continue
        url = _resolve_url(repo_id, fname, revision)
        local_path = os.path.join(dest_dir, f"{split_name}.parquet")
        if not os.path.exists(local_path):
            data = _http_get(url, timeout=300)
            df = _read_table_bytes(fname, data)
            if max_rows and len(df) > max_rows:
                df = df.sample(n=max_rows, random_state=42)
            df.to_parquet(local_path, index=False)
        else:
            df = pd.read_parquet(local_path)
        downloaded[split_name] = local_path
        row_counts[split_name] = int(len(df))

    # Fallback: datasets with no conventional split names (e.g. part-N.csv).
    if not downloaded:
        others = splits.get("other", [])
        fname = _pick_preferred_file(others)
        if fname:
            url = _resolve_url(repo_id, fname, revision)
            local_path = os.path.join(dest_dir, "train.parquet")
            data = _http_get(url, timeout=300)
            df = _read_table_bytes(fname, data)
            if max_rows and len(df) > max_rows:
                df = df.sample(n=max_rows, random_state=42)
            df.to_parquet(local_path, index=False)
            downloaded["train"] = local_path
            row_counts["train"] = int(len(df))

    if not downloaded:
        raise RuntimeError(f"No downloadable data files found for dataset '{repo_id}'.")

    primary = downloaded.get("train") or next(iter(downloaded.values()))
    target = None
    try:
        sample = pd.read_parquet(primary)
        target = _detect_target(sample)
    except Exception:
        pass

    return {
        "repoId": repo_id,
        "revision": revision,
        "url": f"{HF_WEB}/{repo_id}",
        "destDir": dest_dir,
        "splits": downloaded,
        "rowCounts": row_counts,
        "primaryPath": primary,
        "testPath": downloaded.get("test"),
        "targetColumn": target,
        "license": _parse_tags(info.get("tags"))["license"],
    }


# --------------------------------------------------------------------------- #
# Comparison + recommendation
# --------------------------------------------------------------------------- #
def _goal_terms(goal: str) -> List[str]:
    stop = {"improve", "the", "a", "an", "for", "and", "of", "to", "detect",
            "detection", "using", "with", "model", "ml", "better"}
    words = re.findall(r"[a-z]+", (goal or "").lower())
    return [w for w in words if w not in stop and len(w) > 2]


def score_candidate(cand: Dict[str, Any], goal: str) -> Tuple[float, List[str]]:
    """
    Heuristic suitability score with human-readable reasons. Higher = better.
    We never label a dataset "best" without explaining why it is suitable.
    """
    score = 0.0
    reasons: List[str] = []
    terms = _goal_terms(goal)
    blob = " ".join([
        cand.get("repoId", ""), " ".join(cand.get("topics", [])),
        " ".join(cand.get("taskCategories", [])), cand.get("description", ""),
    ]).lower()

    # Relevance to the research goal.
    matches = [t for t in terms if t in blob]
    if matches:
        score += min(len(matches) * 8, 30)
        reasons.append(f"Matches the goal terms: {', '.join(sorted(set(matches)))}.")

    # Tabular classification suitability.
    if "tabular-classification" in cand.get("taskCategories", []) or "tabular" in cand.get("modality", []):
        score += 12
        reasons.append("Structured tabular data suited to classification experiments.")

    if cand.get("format") in ("parquet", "csv"):
        score += 6
        reasons.append(f"Directly loadable {cand.get('format')} format.")

    # Popularity / community trust as a weak quality signal.
    dl = cand.get("downloads") or 0
    if dl >= 1000:
        score += 10
        reasons.append(f"Widely used ({dl:,} downloads).")
    elif dl >= 100:
        score += 5
        reasons.append(f"Moderately used ({dl:,} downloads).")

    if (cand.get("likes") or 0) > 0:
        score += min(cand["likes"], 8)

    # License clarity aids reproducibility.
    if cand.get("license"):
        score += 5
        reasons.append(f"Clear license ({cand['license']}) supports reproducible use.")
    else:
        reasons.append("License not stated — reproducibility may be limited.")

    if cand.get("gated") or cand.get("private"):
        score -= 40
        reasons.append("Gated/private — may require access approval.")

    # Size suitability (enough rows to learn from, not absurdly large).
    size = (cand.get("sizeCategory") or "").lower()
    if any(s in size for s in ("100k", "1m", "10m")):
        score += 6
        reasons.append(f"Substantial data volume ({cand.get('sizeCategory')}).")

    return round(score, 2), reasons


def compare_and_recommend(candidates: List[Dict[str, Any]], goal: str,
                          top_n: int = 4) -> Dict[str, Any]:
    """Score, rank, and pick a recommended dataset with an explanation."""
    scored = []
    for c in candidates:
        s, reasons = score_candidate(c, goal)
        item = dict(c)
        item["score"] = s
        item["reasons"] = reasons
        scored.append(item)

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]
    recommended = top[0] if top else None

    return {
        "goal": goal,
        "candidates": top,
        "recommendation": recommended,
    }
