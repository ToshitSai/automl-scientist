import urllib.request
import urllib.parse
import json
import os
from typing import Dict, Any, List
import backend.config

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_URL = "https://api.openalex.org/works"

def search_semantic_scholar(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    papers = []
    try:
        url = f"{SEMANTIC_SCHOLAR_URL}?query={urllib.parse.quote(query)}&limit={limit}&fields=title,authors,year,abstract,url,citationCount"
        req = urllib.request.Request(url, headers={'User-Agent': 'AutoMLScientistEngine/2.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                for item in data.get("data", []):
                    authors_str = ", ".join([a.get("name", "") for a in item.get("authors", [])[:3]])
                    papers.append({
                        "paperId": item.get("paperId", "s2-pub"),
                        "source": "Semantic Scholar",
                        "title": item.get("title", "Untitled Paper"),
                        "authors": authors_str or "Unknown Authors",
                        "year": item.get("year", 2024),
                        "url": item.get("url") or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}",
                        "abstract": item.get("abstract") or f"Research paper on {query[:40]}...",
                        "relevance": f"High - Citations: {item.get('citationCount', 0)}. Semantic Scholar catalog."
                    })
    except Exception as err:
        print(f"[SEMANTIC SCHOLAR WARNING]: {err}")
    return papers

def search_openalex(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    papers = []
    api_key = os.environ.get("OPENALEX_API_KEY")
    try:
        url = f"{OPENALEX_URL}?search={urllib.parse.quote(query)}&per-page={limit}"
        if api_key:
            url += f"&api_key={api_key}"
            
        req = urllib.request.Request(url, headers={'User-Agent': 'AutoMLScientistEngine/2.0 (mailto:researcher@ai-scientist.io)'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                for item in data.get("results", []):
                    title = item.get("display_name") or item.get("title") or "Untitled OpenAlex Paper"
                    authorships = item.get("authorships", [])
                    authors_list = [a.get("author", {}).get("display_name", "") for a in authorships[:3]]
                    authors_str = ", ".join([a for a in authors_list if a])
                    year = item.get("publication_year", 2024)
                    doi = item.get("doi") or item.get("id", "")
                    
                    papers.append({
                        "paperId": item.get("id", "openalex-pub"),
                        "source": "OpenAlex",
                        "title": title,
                        "authors": authors_str or "OpenAlex Authors",
                        "year": year,
                        "url": doi if doi.startswith("http") else f"https://openalex.org/{item.get('id', '')}",
                        "abstract": f"Academic research indexed in OpenAlex repository on {query[:40]}.",
                        "relevance": f"High - OpenAlex Index. Citations: {item.get('cited_by_count', 0)}."
                    })
    except Exception as err:
        print(f"[OPENALEX API WARNING]: {err}")
    return papers

def search_literature(objective: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Searches Semantic Scholar & OpenAlex APIs for literature search.
    Merges and deduplicates results from both academic databases.
    """
    query = objective
    if "fraud" in objective.lower():
        query = "credit card fraud detection class imbalance precision recall"
    elif "churn" in objective.lower():
        query = "customer churn prediction gradient boosting interpretability"
    elif "price" in objective.lower() or "house" in objective.lower():
        query = "tabular regression house prices feature engineering xgboost"

    s2_papers = search_semantic_scholar(query, limit=limit)
    alex_papers = search_openalex(query, limit=limit)

    all_papers = s2_papers + alex_papers
    
    # Deduplicate by title similarity
    seen_titles = set()
    unique_papers = []
    for p in all_papers:
        norm_title = p["title"].lower().strip()
        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            unique_papers.append(p)

    return unique_papers[:limit*2]
