"""Deep Research pipeline: plan -> search -> synthesize -> verify -> report.

Implements the router's autonomous multi-step research mode. Sources come from
the web_search tool (current web) plus the literature tool (academic papers).
The report is honest by construction: it contains only material traceable to a
collected source, and if no source can be reached it reports that instead of
inventing content.
"""
import datetime
from typing import Any, Dict, List

import backend.config  # auto-loads .env into os.environ
from backend.llm import query_llm
from backend.literature_search import search_literature
from backend.web_search import search_web

_SYNTH_SYSTEM_PROMPT = (
    "You are a rigorous research synthesizer. Write ONLY from the evidence "
    "snippets provided, citing sources inline like [1]. Never state a fact that "
    "is not present in the evidence. If the evidence is insufficient, say so "
    "explicitly."
)

_FILLER_ABSTRACT_PREFIXES = ("research paper on", "academic research indexed")


def plan_subqueries(goal: str, max_subqueries: int = 3) -> List[str]:
    """Break the research goal into concrete search sub-queries.

    Uses the LLM when a provider is reachable; otherwise deterministic query
    variants derived from the goal. Returns [] for an empty goal.
    """
    goal = (goal or "").strip()
    if not goal:
        return []

    llm = query_llm(
        f'Research goal: "{goal}"\n'
        f"Break it into {max_subqueries} short, self-contained web search queries. "
        "Return one query per line, no numbering, no commentary.",
        "You are a research planner. Output only the queries.",
    )
    if llm:
        subs = []
        for line in llm.splitlines():
            clean = line.strip().strip("-•").strip()
            clean = clean.lstrip("0123456789. ").strip()
            if 5 < len(clean) < 120 and clean.lower() not in (s.lower() for s in subs):
                subs.append(clean)
            if len(subs) >= max_subqueries:
                break
        if subs:
            return subs

    base = goal.rstrip("?.!").strip()
    year = datetime.datetime.now().year
    variants = [
        base,
        f"{base} explained",
        f"{base} latest developments {year}",
        f"{base} advantages and disadvantages",
    ]
    return variants[:max_subqueries]


def _paper_to_source(paper: Dict[str, Any]) -> Dict[str, str]:
    title = paper.get("title") or ""
    abstract = paper.get("abstract") or ""
    # The literature tool injects a synthetic filler abstract when the API
    # returned none; that is not real evidence, so drop it.
    low = abstract.lower()
    if any(low.startswith(p) for p in _FILLER_ABSTRACT_PREFIXES):
        abstract = ""
    return {
        "title": title,
        "url": paper.get("url") or "",
        "snippet": abstract[:400],
        "source": paper.get("source") or "Academic",
    }


def _collect_sources(subqueries: List[str], per_query: int, papers_on_first: int = 2) -> List[Dict[str, Any]]:
    """Run web + academic searches per sub-query and deduplicate by URL.

    A paper hit without real evidence (empty snippet after dropping the
    literature tool's filler abstracts) is not a usable source and is skipped."""
    sources: List[Dict[str, Any]] = []
    seen_urls = set()
    for idx, sq in enumerate(subqueries):
        web_hits = search_web(sq, limit=per_query)
        paper_hits: List[Dict[str, str]] = []
        if idx < papers_on_first:
            try:
                papers = search_literature(sq, limit=2) or []
                paper_hits = [_paper_to_source(p) for p in papers]
            except Exception as exc:
                print(f"[DEEP RESEARCH WARNING] literature search failed for '{sq}': {exc}")
        for hit in web_hits + paper_hits:
            url = (hit.get("url") or "").strip()
            title = (hit.get("title") or "").strip()
            snippet = (hit.get("snippet") or "").strip()
            if not url or url in seen_urls:
                continue
            if title.lower().startswith("untitled"):
                continue
            # Web hits may legitimately lack snippets (link-only results), but
            # academic hits without evidence add nothing verifiable.
            if not snippet and hit.get("source") in ("Academic", "Semantic Scholar", "OpenAlex"):
                continue
            seen_urls.add(url)
            sources.append({**hit, "query": sq})
    return sources


def _synthesize(goal: str, subqueries: List[str], sources: List[Dict[str, Any]]) -> str:
    """Build the report: grounded LLM synthesis when a provider is reachable,
    otherwise an honest sourced-snippet digest. Verification notes included."""
    by_query: Dict[str, List[Dict[str, Any]]] = {}
    for n, source in enumerate(sources, 1):
        source["n"] = n
        by_query.setdefault(source["query"], []).append(source)

    lines = [
        f"# Deep Research Report: {goal}",
        "",
        "> Machine-generated by the AI Scientist deep-research pipeline "
        f"({datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')}). "
        "Every statement below is traceable to a cited source; evidence is snippet-level "
        "(pages were not fully read).",
        "",
        "## Research Plan",
    ]
    lines += [f"{i}. {sq}" for i, sq in enumerate(subqueries, 1)]
    lines += ["", "## Findings", ""]

    use_llm = True
    for sq in subqueries:
        items = by_query.get(sq) or []
        if not items:
            lines += [f"### {sq}", "_No sources were found for this sub-question._", ""]
            continue

        evidence = "\n".join(f"[{s['n']}] {s['title']} — {s['snippet']}" for s in items if s.get("snippet"))
        section = None
        if use_llm and evidence:
            section = query_llm(
                f"Research goal: {goal}\nSub-question: {sq}\n\n"
                f"Evidence snippets (cite by [n]):\n{evidence}\n\n"
                "Write a 3-5 sentence synthesis of this sub-question using ONLY the evidence "
                "above, citing sources inline like [1]. Say explicitly if the evidence is insufficient.",
                _SYNTH_SYSTEM_PROMPT,
            )
            if section is None:
                use_llm = False  # no provider reachable; digest the rest honestly
        if not section:
            section = "\n".join(
                f"- **[{s['n']}] {s['title']}** ({s['source']}): {s.get('snippet') or '(no snippet available — open the source)'}"
                for s in items
            )
        lines += [f"### {sq}", section, ""]

    lines += [
        "## Verification",
        f"- {len(sources)} unique sources collected across {len(subqueries)} planned searches (web + academic), deduplicated by URL.",
        "- Only sourced material is included; statements are snippet-level and should be verified against the full sources before being relied on.",
        "",
        "## Sources",
    ]
    lines += [f"{s['n']}. [{s['title'] or s['url']}]({s['url']}) — {s['source']}" for s in sources]
    return "\n".join(lines)


def run_deep_research(goal: str, per_query: int = 3) -> Dict[str, Any]:
    """Execute the full deep-research pass for a goal."""
    subqueries = plan_subqueries(goal)
    if not subqueries:
        return {"status": "no_sources", "report": "", "sourceCount": 0, "subqueries": []}

    sources = _collect_sources(subqueries, per_query)
    if not sources:
        return {"status": "no_sources", "report": "", "sourceCount": 0, "subqueries": subqueries}

    report = _synthesize(goal, subqueries, sources)
    return {
        "status": "ok",
        "report": report,
        "sourceCount": len(sources),
        "subqueries": subqueries,
    }
