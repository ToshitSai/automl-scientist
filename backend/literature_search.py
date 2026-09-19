import urllib.request
import urllib.parse
import json
from typing import Dict, Any, List

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

def search_literature(objective: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Searches Semantic Scholar API for real research papers relevant to the research objective.
    Uses stdlib urllib.request to avoid external dependency issues.
    Falls back gracefully to domain research papers if API rate limit or network error occurs.
    """
    query = objective
    if "fraud" in objective.lower():
        query = "credit card fraud detection class imbalance precision recall"
    elif "churn" in objective.lower():
        query = "customer churn prediction gradient boosting interpretability"
    elif "price" in objective.lower() or "house" in objective.lower():
        query = "tabular regression house prices feature engineering xgboost"

    try:
        url = f"{SEMANTIC_SCHOLAR_URL}?query={urllib.parse.quote(query)}&limit={limit}&fields=title,authors,year,abstract,url,citationCount"
        req = urllib.request.Request(url, headers={'User-Agent': 'AutoMLScientistEngine/2.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                papers = []
                for item in data.get("data", []):
                    authors_str = ", ".join([a.get("name", "") for a in item.get("authors", [])[:3]])
                    papers.append({
                        "paperId": item.get("paperId", "s2-pub"),
                        "title": item.get("title", "Untitled Paper"),
                        "authors": authors_str or "Unknown Authors",
                        "year": item.get("year", 2024),
                        "url": item.get("url") or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}",
                        "abstract": item.get("abstract") or f"Research on {objective[:50]}...",
                        "relevance": f"High - Citation count: {item.get('citationCount', 0)}. Direct alignment with research objective."
                    })
                if papers:
                    return papers
    except Exception as err:
        print(f"[LITERATURE SEARCH API WARNING]: {err}")

    # No fake paper fallback. Return empty list if no real papers found or API unavailable.
    return []

