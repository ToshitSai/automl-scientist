"""Current-information pipeline (repair directive: current-fact questions).

Architecture:

    CURRENT QUESTION
      -> detect time sensitivity (generic patterns: "who won X", "current CEO
         of X", "latest <product>", prices, future-year questions)
      -> focus the query (entity + aspect + event year)
      -> search/retrieve with source priority (keyed web providers when
         configured; keyless Wikipedia article API otherwise)
      -> verify: source RELEVANCE (entity actually matches) + DATE support
         (article covers the event year / current year; future events fail)
      -> extract the requested fact sentence (question-intent scoring)
      -> direct answer + source

Never substitutes related background for the requested fact: when the fact
cannot be extracted, the answer says so ("I can't reliably verify ...")
instead of pasting an edition/history summary. Never hard-codes any entity:
every step is generic over the parsed question, so it works for sports,
politics, tech, business, prices, leadership, etc.

Result shape (structured, for the API layer — not exposed as raw JSON text):

    {"status": "ok" | "unavailable", "question", "answer", "sources",
     "verified", "reason"}
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_USER_AGENT = "AI-Scientist-Assistant/1.0 (current-information tool)"
_HTTP_TIMEOUT = 10

# Small TTL cache for page/title lookups: a question probes several candidate
# pages, bursts of questions re-fetch the same ones, and public endpoints
# throttle aggressive clients. Caching keeps bursts gentle and answers stable.
_CACHE: Dict[str, tuple] = {}
_CACHE_TTL = 600          # seconds
_CACHE_MAX = 128


def _cache_get(key: str):
    entry = _CACHE.get(key)
    if entry is None:
        return None
    if time.time() - entry[0] > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return entry[1]


def _cache_put(key: str, value) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
        _CACHE.pop(oldest, None)
    _CACHE[key] = (time.time(), value)


# Sentinel: "the page genuinely does not exist" (safe to cache — e.g. a future
# edition's page). A TRANSIENT request failure must never be cached, or one
# network blip would hide an answerable question behind "cannot verify" for
# the whole TTL.
_PAGE_MISSING = object()

# ---------------------------------------------------------------------------
# 1. Time-sensitivity detection + question parsing (generic, no entity list)
# ---------------------------------------------------------------------------

@dataclass
class CurrentInfoRequest:
    question: str
    entity: str                # "IPL" / "Microsoft" / "NVIDIA GPU"
    aspect: str                # "champion" | "holder" | "price" | "latest"
    year: Optional[int]        # explicit event year, if any
    query: str                 # focused search query

# Patterns that mark a question as needing current factual verification.
# Deliberately structural (question shape), never entity-specific.
_CURRENT_FACT_RE = re.compile(
    r"\bwho\s+won\b"
    r"|\bwho\s+(?:is|was|are|were)\s+(?:the\s+)?(?:current|present|incumbent|new|reigning)\b"
    r"|\bwho\s+is\s+(?:the\s+)?(?:ceo|cto|cfo|coo|president|prime\s+minister|"
    r"chancellor|chairman|owner|captain|coach|governor|mayor)\s+of\b"
    r"|\bwho\s+(?:was|were|is|are)\s+(?:the\s+)?runners?[-\s]?up\b"
    r"|\bwhat(?:'s|\s+is|\s+was)\s+the\s+(?:current|latest|newest|new|reigning)\s+"
    r"(?!news\b|about\b|developments\b|updates\b|research\b)[a-z0-9][a-z0-9 \-]{1,40}$"
    r"|\b(?:current|latest|live|today's|todays|now)\s+(?:[a-z0-9]+\s+){0,3}?"
    r"(?:price|stock\s+price|share\s+price|score|version|weather|temperature|"
    r"forecast)\b",
    re.IGNORECASE,
)

_NEWS_RE = re.compile(r"\bnews\b|\bwhat\s+happened\b|\bdevelopments\b|\bthis\s+week\b",
                      re.IGNORECASE)

_STRIP_FOR_ENTITY = re.compile(
    r"\b(?:who|what|whats|won|is|was|are|were|the|a|an|current|currently|present|"
    r"incumbent|new|newest|latest|reigning|of|in|for|to|by|price|stock|share|"
    r"ceo|cto|cfo|president|captain|coach|owner|chairman|winner|winner\s+of|"
    r"runners?|up|today|todays|now|live)\b",
    re.IGNORECASE,
)

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def extract_current_fact_request(message: str) -> Optional[CurrentInfoRequest]:
    """Parse a message into a current-fact request, or None when the message
    is not a current-fact question (news lists, research commands, general
    knowledge and everything else stay with their own intents)."""
    if not message:
        return None
    text = message.strip()
    if _NEWS_RE.search(text) and not re.search(r"\bwho\s+won\b", text, re.IGNORECASE):
        return None                      # news listings are WEB_SEARCH's job
    # Trailing punctuation must not break end-anchored patterns
    # ("What is the latest NVIDIA GPU?").
    m = _CURRENT_FACT_RE.search(text.rstrip("?!. \t"))
    if not m:
        return None

    year_m = _YEAR_RE.search(text)
    year = int(year_m.group(1)) if year_m else None
    entity = _STRIP_FOR_ENTITY.sub(" ", text)
    entity = re.sub(r"'\s*s\b", " ", entity)
    entity = re.sub(r"\s+-\s*", " ", entity)
    entity = re.sub(r"[?!.,;:]", " ", entity)
    entity = re.sub(r"\b(19|20)\d{2}\b", " ", entity)
    entity = re.sub(r"\s+", " ", entity).strip()
    if len(entity.split()) > 6:
        return None                      # runaway parse — stay out of the way
    if not entity:
        return None

    low = text.lower()
    if re.search(r"runners?\s*[-\s]?up|came\s+second", low):
        aspect = "runner_up"
    elif "who won" in low or "champion" in low:
        aspect = "champion"
    elif re.search(r"\b(?:ceo|cto|cfo|president|captain|coach|owner|chairman)\b", low):
        aspect = "holder"
    elif re.search(r"\bprice\b|\bstock\b", low):
        aspect = "price"
    else:
        aspect = "latest"

    if aspect in ("champion", "runner_up"):
        query = (f"{entity} {year} final winner" if year
                 else f"{entity} latest final winner")
    elif aspect == "holder":
        query = f"{entity} current CEO" if "ceo" in low else f"{entity} current"
    elif aspect == "price":
        query = f"{entity} current price"
    else:
        query = f"latest {entity}"
    return CurrentInfoRequest(question=text, entity=entity, aspect=aspect,
                              year=year, query=query)


# ---------------------------------------------------------------------------
# 2. Source retrieval (keyed web providers when configured, else keyless
#    Wikipedia article API — real source priority, no fabricated sources)
# ---------------------------------------------------------------------------

def _http_json(url: str) -> Dict:
    """GET a JSON URL with bounded retries — public endpoints (e.g. Wikipedia)
    drop or rate-limit occasional requests, and a transient failure must not
    turn an answerable question into 'cannot verify'."""
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as err:            # noqa: BLE001 — any transport error retries
            last_err = err
            if attempt < 2:
                time.sleep(0.6 if attempt == 0 else 1.5)
    raise last_err


def _search_web(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """Keyed providers via the existing search tool; keyless DDG/Wikipedia
    fallback. Returns [] when nothing real is found — never fake results."""
    try:
        from backend.web_search import search_web
        return search_web(query, limit=limit) or []
    except Exception:
        return []


_TITLE_QUALIFIER_RE = re.compile(r"\b(women'?s|under-?19|u-?19|junior|youth)\b",
                                re.IGNORECASE)  # NOTE: "Men's" is NOT a qualifier — the men's/senior edition is the default


def _fetch_page(title: str) -> Optional[Dict[str, str]]:
    key = f"page:{title}"
    cached = _cache_get(key)
    if cached is not None:
        return None if cached is _PAGE_MISSING else cached
    result = _fetch_page_uncached(title)
    if result is _PAGE_MISSING:
        _cache_put(key, _PAGE_MISSING)   # real negative — cache it
        return None
    if result is not None:               # transient failure — NOT cached
        _cache_put(key, result)
    return result


def _fetch_page_uncached(title: str) -> Optional[Dict[str, str]]:
    try:
        page = _http_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "prop": "extracts|revisions", "explaintext": 1,
            "redirects": 1, "rvprop": "timestamp", "rvlimit": 1,
            "format": "json", "titles": title}))
        pages = (page.get("query") or {}).get("pages") or {}
        data = next(iter(pages.values()), {})
        if "missing" in data or not data.get("extract"):
            return _PAGE_MISSING
        modified = ""
        revs = (data.get("revisions") or [{}])
        if revs and isinstance(revs, list):
            modified = (revs[0].get("timestamp") or "")[:10]
        return {
            "title": data.get("title") or title,
            "extract": _clean_wiki_text(data["extract"]),
            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                (data.get("title") or title).replace(" ", "_")),
            "modified": modified,
        }
    except Exception:
        return None


def _ranked_search_titles(search_terms: str, year: Optional[int]) -> List[str]:
    """Search hits for `search_terms`, ranked for the requested event year:
    drop pages whose TITLE names a different year (a 2027-edition page must
    never answer a 2026 question), and prefer pages without gender/junior
    qualifiers the question didn't ask for."""
    cache_key = f"titles:{search_terms}|{year}"
    cached = _cache_get(cache_key)
    if cached is not None or cache_key in _CACHE:
        return list(cached or [])
    try:
        search = _http_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": search_terms,
            "srlimit": 5, "format": "json"}))
    except Exception:
        return []
    hits = [h["title"] for h in (search.get("query") or {}).get("search", [])]
    ranked, deferred = [], []
    now = _dt.datetime.now(_dt.timezone.utc)
    for title in hits:
        title_years = {int(y) for y in _YEAR_RE.findall(title)}
        if year and title_years and year not in title_years:
            continue                     # different edition — never answer with it
        if not year and title_years and min(title_years) > now.year:
            continue                     # future edition ("next World Cup") — unanswerable
        quals = {q.lower().replace("'", "") for q in _TITLE_QUALIFIER_RE.findall(title)}
        if quals and not any(q in search_terms.lower() for q in quals):
            deferred.append(title)       # "Women's ..." when not asked — last resort
            continue
        ranked.append(title)
    out = ranked + deferred
    _cache_put(cache_key, out)
    return out


def _wiki_titles_for(entity: str, year: Optional[int]) -> List[str]:
    """Candidate page titles for the entity (+year): ranked search hits first,
    then the direct edition-title probe ("<Entity> <Year>")."""
    titles = _ranked_search_titles(f"{entity} {year}" if year else entity, year)
    if year:
        direct = f"{entity} {year}"
        if direct not in titles:
            titles.append(direct)
    return titles


def _clean_wiki_text(extract: str) -> str:
    """Drop section headers ('== Background ==') and collapse whitespace so
    sentence splitting sees prose only."""
    no_headers = re.sub(r"^\s*==+[^=]+==+\s*$", "", extract or "", flags=re.M)
    return re.sub(r"[ \t]+", " ", no_headers)


def _year_candidates(req: CurrentInfoRequest) -> List[Optional[int]]:
    """Which event-year pages to try, in order. Recurring events (world cups,
    league seasons, awards) name a page per edition: without an explicit year
    the latest edition is current_year, falling back to the previous one."""
    now = _dt.datetime.now(_dt.timezone.utc)
    if req.year:
        return [req.year]
    return [now.year, now.year - 1]


# ---------------------------------------------------------------------------
# 3. Verification: relevance + date support
# ---------------------------------------------------------------------------

_GENERIC_TOKENS = {"league", "cup", "series", "tournament", "final", "season",
                   "championship", "latest", "current", "new", "price", "version"}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def _sentences(text: str) -> List[str]:
    # List-style blocks ("Satya Nadella (2014–present)") are line-separated,
    # not period-separated — split on newlines first, then on sentence ends.
    lines = []
    for line in (text or "").split("\n"):
        lines.extend(_SENTENCE_SPLIT_RE.split(line))
    return [s.strip() for s in lines if s.strip()]


def _entity_tokens(entity: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z][A-Za-z\-]+", entity)
            if t.lower() not in _GENERIC_TOKENS and len(t) > 1]


def _relevance_ok(req: CurrentInfoRequest, page: Dict[str, str]) -> bool:
    """The page must actually be ABOUT the entity (title or intro head matches
    the entity's significant tokens or its acronym) — not just any page that
    mentions one of the words."""
    hay = (page.get("title", "") + " " + page.get("extract", "")[:400]).lower()
    toks = _entity_tokens(req.entity)
    if not toks:
        return False
    acronym = req.entity.isupper() and len(req.entity) <= 6
    if acronym and req.entity.lower() in hay:
        return True
    matched = sum(1 for t in toks if t.lower() in hay)
    return matched >= max(1, len(toks) - 1)


def _date_supports(req: CurrentInfoRequest, page: Dict[str, str]) -> bool:
    """Publication/update sanity (§7): the article must cover the event year,
    or (no explicit year) the current year. Future events can never verify."""
    now = _dt.datetime.now(_dt.timezone.utc)
    current_year = now.year
    if req.year and req.year > current_year:
        return False                    # future event — not answerable
    extract = page.get("extract", "")
    if req.year:
        return str(req.year) in extract or str(req.year) in page.get("title", "")
    # No explicit year: require a recency signal — current year in the article,
    # a title naming the current or previous edition year, current/latest
    # wording near the top, or a revision (publication) date in the current
    # year — the update timestamp IS a publication-date signal (§7/§8).
    title_years = {int(y) for y in _YEAR_RE.findall(page.get("title", ""))}
    if title_years and max(title_years) >= current_year - 1:
        return True
    if (page.get("modified") or "")[:4] == str(current_year):
        return True
    return (str(current_year) in extract
            or str(current_year) in page.get("title", "")
            or "current" in extract[:800].lower()
            or "latest" in extract[:800].lower())


_INCEPTION_RE = re.compile(
    r"\b(?:founded|established|inaugural|first\s+held|first\s+season|first\s+"
    r"edition|began|started|created|launched|formed)\s+(?:in\s+)?(1[89]\d\d|20\d\d)\b",
    re.IGNORECASE)


def _entity_inception_year(entity: str) -> Optional[int]:
    """Earliest inception/first-edition year stated in the entity's base article
    ("founded in 2008", "inaugural season in 2008"), or None when unknown. Used
    for GENERIC invalid-premise detection: a dated result for a year before the
    entity existed can never be verified because it never happened (§4/§5)."""
    titles = [t for t in _wiki_titles_for(entity, None)][:1]
    for title in titles:
        page = _fetch_page(title)
        if not page:
            continue
        years = [int(y) for y in _INCEPTION_RE.findall(page.get("extract", "")[:1200])]
        if years:
            return min(years)
    return None


# ---------------------------------------------------------------------------
# 4. Fact extraction (question-intent scoring — no entity knowledge)
# ---------------------------------------------------------------------------

_ASPECT_KEYWORDS = {
    "champion": {
        "pos": ["won the final", "defeated", "defeating", "beat", "champions",
                "champion", "lifted", "crowned", "won their", "won its",
                "title winners", "emerged victorious", "clinched", "victory",
                "sealed", "triumph", "won by"],
        "neg": ["edition", "scheduled", "featured", "venues", "schedule",
                "broadcast", "branding", "was announced", "known as",
                "participated", "points table", "playoff", "qualification",
                "promotion", "cycle", "relegation", "previous season",
                "having won", "were confirmed", "inaugural match",
                "match against", "matches against", "group stage",
                "league stage", "their next"],
    },
    "holder": {
        "pos": ["chief executive", "ceo", "president", "serves as", "incumbent",
                "has held", "took office", "appointed", "serves", "served as",
                "became", "named"],
        "neg": ["former", "predecessor", "preceded", "list of", "vice",
                "stated", "said", "according to", "joining", "join",
                "resigned", "ousted", "division", "subsidiary", "department",
                "renamed", "available for customers", "insider program"],
    },
    "price": {
        "pos": ["us$", "$", "traded", "price", "valuation", "market cap"],
        "neg": ["history of", "originally", "introduced in"],
    },
    "runner_up": {
        "pos": ["runner-up", "runners-up", "runner up", "finished second",
                "second place", "lost the final", "lost to", "defeated",
                "defeating", "beat"],
        "neg": ["edition", "scheduled", "featured", "venues", "schedule",
                "broadcast", "branding", "was announced", "known as",
                "participated", "points table", "playoff", "qualification",
                "promotion", "cycle", "relegation"],
    },
    "latest": {
        "pos": ["released", "launched", "current generation", "successor",
                "unveiled", "announced", "current"],
        "neg": ["discontinued", "legacy", "predecessor"],
    },
}


_HOLDER_ROLE_RE = re.compile(
    r"\b(ceo|cto|cfo|coo|president|prime\s+minister|chancellor|chairman|"
    r"owner|captain|coach|governor|mayor)\b", re.IGNORECASE)

# Which ORGANISATION a sentence attributes the office to ("Anthropic's CEO ...",
# "... the CEO of Anthropic"). Used to reject cross-entity office claims.
_ROLE_OWNER_POSSESSIVE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9'&.\-]+(?:\s+[A-Z][A-Za-z0-9'&.\-]+){0,3})['’]s\s+"
    r"(?:ceo|chief executive|president|chairman|chief \w+ officer)\b",
    re.IGNORECASE)
_ROLE_OWNER_OF_RE = re.compile(
    r"\b(?:ceo|chief executive|president|chairman|chief \w+ officer)\s+of\s+"
    r"([A-Z][A-Za-z0-9'&.\-]+(?:\s+[A-Z][A-Za-z0-9'&.\-]+){0,3})",
    re.IGNORECASE)


def _sentence_role_owner(sentence: str) -> Optional[str]:
    """The organisation a sentence ties the office to, or None when unnamed."""
    m = (_ROLE_OWNER_POSSESSIVE_RE.search(sentence or "")
         or _ROLE_OWNER_OF_RE.search(sentence or ""))
    return m.group(1).strip() if m else None


def _owner_matches_entity(owner: str, entity: str) -> bool:
    """True when the office-holding organisation IS the requested entity."""
    o = (owner or "").lower().strip()
    e = (entity or "").lower().strip()
    if not o or not e:
        return False
    if e in o or o in e:
        return True
    etoks = _entity_tokens(entity)
    return any(t in o for t in etoks)


_ROLE_PHRASE = (r"(?:ceo|chief executive officer|chief executive|president|"
                r"chairman|chief \w+ officer|chief \w+ \w+ officer)")


def _entity_owned_role(sentence: str, entity: str) -> Optional[str]:
    """The office the sentence gives to the ENTITY itself ("<Entity>'s CTO",
    "the CEO of <Entity>"), or None when the entity holds no named office."""
    e = re.escape((entity or "").strip())
    if not e:
        return None
    m = re.search(rf"\b{e}['’]s\s+([a-z\s]{{0,28}}?{_ROLE_PHRASE})\b",
                  sentence or "", re.IGNORECASE)
    if not m:
        m = re.search(rf"\b({_ROLE_PHRASE})\s+of\s+{e}\b", sentence or "",
                      re.IGNORECASE)
    return m.group(1).strip().lower() if m else None


def _role_matches_request(owned_role: str, roles: List[str]) -> bool:
    """True when the office named for the entity is the one being asked about."""
    owned = (owned_role or "").lower()
    for role in roles:
        if role == "ceo":
            if "chief executive" in owned or re.search(r"\bceo\b", owned):
                return True
        elif role in owned:
            return True
    return False


def _holder_incumbency(sentence: str, roles: List[str], entity: str) -> bool:
    """True when the sentence states incumbency of the requested office tied to
    the ENTITY ("<Person> is the CEO of <Entity>", "<Entity> is led by CEO
    <Person>", "<Entity>'s CEO is <Person>"), rather than an unrelated anecdote."""
    low = (sentence or "").lower()
    e = re.escape((entity or "").strip())
    for role in roles:
        if not re.search(rf"\b{role}\b", low):
            continue
        if re.search(rf"\bis\s+(?:the\s+)?(?:current\s+)?{role}\b", low) \
           or re.search(rf"\bserves?\s+as\s+(?:the\s+)?{role}\b", low) \
           or re.search(rf"\bbecame\s+(?:the\s+)?{role}\b", low) \
           or re.search(rf"\bwas\s+named\s+(?:the\s+)?{role}\b", low) \
           or re.search(rf"\btook\s+over\s+as\s+(?:the\s+)?{role}\b", low) \
           or re.search(rf"\bled by\b[^.]{{0,40}}\b{role}\b", low) \
           or re.search(rf"{e}['’]s\s+{role}\b", low) \
           or re.search(rf"\b{role}\s+of\s+{e}\b", low):
            return True
    return False

# Structural (entity-free) signals that a sentence states the FINAL RESULT of
# an event, not season context: a win margin ("by 6 runs") and a purpose
# clause ("... to win their maiden title"). Schedule/context sentences never
# carry these.
_RESULT_BONUS_PATTERNS = {
    "champion": [
        (re.compile(r"\bby\s+\d+\s+(?:wickets?|runs?)\b", re.IGNORECASE), 3),
        (re.compile(r"\bto\s+(?:win|secure|claim|lift)\b", re.IGNORECASE), 2),
    ],
    "runner_up": [
        (re.compile(r"\bby\s+\d+\s+(?:wickets?|runs?)\b", re.IGNORECASE), 3),
    ],
}


def _question_roles(req: CurrentInfoRequest) -> List[str]:
    return [m.group(1).lower() for m in _HOLDER_ROLE_RE.finditer(req.question)]


def _leading_proper_phrase(sentence: str) -> Optional[str]:
    """Leading proper-noun phrase of a sentence ("India were the defending
    champions" -> "India") — used for pronoun resolution."""
    m = re.match(r"\s*((?:[A-Z][\w'&.\-]+\s+){1,4})", sentence or "")
    return m.group(1).strip() if m else None


def _resolve_pronoun(sentence: str, prev_sentence: str) -> str:
    """Resolve a sentence-initial pronoun ("They defended their title by ...")
    against the previous sentence's subject, so the ANSWER names the entity
    instead of an unresolvable pronoun. Returns the original sentence when no
    antecedent can be found."""
    m = re.match(r"^(They|He|She|It)\b\s*(.*)$", sentence.strip(), re.IGNORECASE)
    if not m:
        return sentence
    antecedent = _leading_proper_phrase(prev_sentence or "")
    if not antecedent:
        return sentence
    rest = m.group(2)
    if not rest:
        return sentence
    return f"{antecedent} {rest[0].lower() + rest[1:]}"


def _extract_answer_sentence(req: CurrentInfoRequest, extract: str,
                             entity_bound: bool = False) -> Optional[str]:
    """Pick the ONE sentence that actually answers the question. Returns None
    when no sentence carries the fact — the caller must then admit it cannot
    verify rather than paste background. Requires a positive aspect keyword
    (proper nouns alone never qualify — fixes wrong-sentence extraction)."""
    kws = _ASPECT_KEYWORDS.get(req.aspect) or _ASPECT_KEYWORDS["latest"]
    entity_toks = [t.lower() for t in _entity_tokens(req.entity)]
    roles = _question_roles(req) if req.aspect == "holder" else []
    best, best_score = None, 0
    sents = _sentences(extract)
    for i, s in enumerate(sents):
        # "They defended their title by defeating ..." must be answered with
        # the entity it refers to, not the pronoun.
        if i > 0:
            s = _resolve_pronoun(s, sents[i - 1])
        low = s.lower()
        kw_score = sum(2 for k in kws["pos"] if k in low) \
            - sum(3 for k in kws["neg"] if k in low)
        if kw_score <= 0:
            continue                     # a fact needs a fact-shaped sentence
        core_ok = any(t in low for t in entity_toks)
        # A holder question asks who holds the office OF THE REQUESTED ENTITY.
        # A sentence that ties the role to a DIFFERENT organisation
        # ("Anthropic's CEO published ..." on an OpenAI page) is not evidence
        # for it — reject rather than answer with the wrong company's executive
        # (§11: the source must actually support the asked fact).
        if req.aspect == "holder":
            owner = _sentence_role_owner(s)
            if owner and not _owner_matches_entity(owner, req.entity):
                continue
            owned_role = _entity_owned_role(s, req.entity)
            if owned_role and not _role_matches_request(owned_role, roles):
                continue
            if not _holder_incumbency(s, roles, req.entity):
                continue
        # On a page ABOUT the entity, the fact is often stated with the entity
        # implied — edition pages say "Delta Lions defeated Alpha Kings in the
        # final", not "... in the Nova League final". When the PAGE itself was
        # already bound to the entity (+year) by the relevance/date gates
        # (entity_bound), the sentence need not repeat the entity name; for
        # loosely-matched fallback pages and snippets it must.
        if not core_ok and not entity_bound and req.aspect not in ("holder", "latest"):
            continue
        # Price questions must be answered from live market data, never from a
        # stale historical valuation in an encyclopedia article (§6: wrong to
        # answer "current Bitcoin price" with "US$1 billion, a bubble ...").
        if req.aspect == "price":
            continue
        # "Latest" asks for the CURRENT item: the sentence must carry a
        # freshness signal (current/previous year, or latest/newest/current
        # wording) so a 1999 release can never answer "latest NVIDIA GPU".
        if req.aspect == "latest" and not (
                re.search(r"\b(?:latest|newest|current)\b", low)
                or any(int(y) >= _dt.datetime.now(_dt.timezone.utc).year - 1
                       for y in _YEAR_RE.findall(s))):
            continue
        # A dated question must be answered by a sentence about THAT event:
        # when the year appears in the sentence, it must be the right one
        # (blocks "2011 Champions League ... runner-up in the IPL" answering
        # a 2025 question); when the year doesn't appear anywhere in the
        # sentence, the sentence must still be anchored in the edition via
        # its subject ("<Team> season"-style pages) or the entity itself.
        if req.year:
            sent_years = set(_YEAR_RE.findall(s))
            if sent_years and str(req.year) not in sent_years:
                continue
            if not sent_years and not entity_bound \
                    and req.year != _dt.datetime.now(_dt.timezone.utc).year \
                    and not re.match(rf"^[A-Z0-9].{{0,60}}?\b{re.escape(req.entity.split()[0]) if req.entity.split() else ''}\b",
                                     s, re.IGNORECASE):
                continue
        score = kw_score
        for pat, weight in _RESULT_BONUS_PATTERNS.get(req.aspect, []):
            if pat.search(low):
                score += weight
        # Holder questions: present-tense office patterns ("X is the CEO of
        # Y", "serves as the CEO", "X became CEO in 2014") outrank historical
        # anecdotes about other people.
        if roles:
            for role in roles:
                if re.search(rf"\b(?:is|are)\s+(?:the\s+)?[a-z\-]{{0,30}}?{role}\b", low) \
                        or re.search(rf"\b(?:serves?|served|appointed|named|became)\s+"
                                     rf"(?:as\s+)?(?:the\s+)?[a-z\-]{{0,30}}?{role}\b", low) \
                        or (re.search(rf"{role}\s+of\b", low) and " current" in low) \
                        or re.search(rf"\bled by\b[^.]*\b{role}\b", low) \
                        or re.search(rf"\b{role}\b\s+[A-Z][a-z]{{2,}}", s):
                    score += 6
            if re.search(r"\b(?:on|in)\s+(?:january|february|march|april|may|june|"
                         r"july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b",
                         low):
                score -= 3               # dated anecdote, likely not the incumbent
        # Proper-noun payload as a tiebreak only.
        proper = len(re.findall(r"\b[A-Z][a-z]{2,}\b", s))
        score += min(proper, 4) // 2
        if score > best_score and len(s) < 400:
            best, best_score = s, score
    return best if best is not None else None


# ---------------------------------------------------------------------------
# 5. Pipeline entry point
# ---------------------------------------------------------------------------

def _runner_up_answer(sentence: str) -> Optional[str]:
    """For runner-up questions, derive the runner-up from a verified final
    sentence. Both directions are handled from the SAME evidence sentence:
      - "X lost to Y" / "X were beaten by Y"      -> X is the runner-up
      - "X defeated Y in the final" / "X beat Y"  -> Y is the runner-up
      - a sentence already naming a runner-up     -> kept as-is
    Returns None when the sentence cannot be safely derived from (caller then
    admits it cannot verify rather than mislabeling the winner)."""
    s = sentence.strip()
    m = re.search(
        r"\b(.{3,120}?)\s+(?:lost (?:to|the final (?:to|against))|"
        r"were beaten by|was beaten by|finished (?:as )?runners?-?up\s+"
        r"(?:to|behind))\s+(.{3,120}?)[.,]", s, re.IGNORECASE)
    if m:
        return (f"{m.group(1).strip()} were the runners-up, losing to "
                f"{m.group(2).strip().rstrip('. ')}.")
    m = re.search(
        r"\b(.{3,120}?)\s+(?:defeated|beat|overcame)\s+(.+)$",
        s, re.IGNORECASE)
    if m:
        loser = m.group(2).strip()
        # Cut the margin / venue tail: "... Gujarat Titans by 5 wickets in the
        # final to secure ..." -> "Gujarat Titans".
        loser = re.split(r"\s+by\s+|\s+in\s+the\s+(?:final|match|series)|[.;]",
                         loser, maxsplit=1)[0].strip()
        winner = re.sub(
            r"^(?:defending |reigning |then )?champions?\s+", "", m.group(1).strip(),
            flags=re.IGNORECASE)
        # "India won the 2025 World Cup after defeating X" -> winner is India,
        # not the whole lead-up clause.
        winner = re.split(r"\s+won\b.*$", winner)[0].strip().rstrip(" ,;")
        if loser:
            return (f"{loser} were the runners-up, losing to {winner} in the final.")
    if re.search(r"\brunners?-?up\b|\bfinished second\b", s, re.IGNORECASE):
        return s                                # already states the runner-up
    return None


def answer_current_fact(req: Optional[CurrentInfoRequest],
                        search_fn: Optional[Callable] = None) -> Optional[Dict]:
    """Answer a current-fact request, or return an honest unavailability.

    Returns None only when `req` is None (caller should use another intent).
    """
    if req is None:
        return None
    now = _dt.datetime.now(_dt.timezone.utc)
    sources: List[Dict[str, str]] = []

    # Future events can never verify — say so without searching.
    if req.year and req.year > now.year:
        return {
            "status": "unavailable", "question": req.question,
            "answer": (f"I can't verify a result for {req.year} {req.entity}: that "
                       f"event hasn't taken place yet (current year is {now.year}), "
                       "and I won't invent one."),
            "sources": [], "verified": False, "reason": "future_event",
        }

    # Invalid-premise check (§4/§5): a dated result for a year BEFORE the entity
    # existed can never be verified because it never happened. Detect this from
    # the entity's own inception/first-edition year (generic — no per-entity
    # knowledge) and correct the premise instead of claiming search failed.
    if req.year and req.year < now.year:
        inception = _entity_inception_year(req.entity)
        if inception is not None and req.year < inception:
            return {
                "status": "invalid_premise", "question": req.question,
                "answer": (
                    f"The premise appears to be incorrect: {req.entity} did not "
                    f"exist in {req.year} (it began around {inception}), so there "
                    f"is no {req.year} result to report. If you meant a different "
                    f"year from {inception} onward, tell me the year and I'll check."
                ),
                "sources": [], "verified": False, "reason": "invalid_premise",
            }

    # 1) Keyless structured source: Wikipedia article (relevance+date checked).
    #    Without an explicit year, recurring events are tried per edition
    #    (current year, then previous) so "latest X winner" resolves.
    def _try_page(page: Dict[str, str]) -> Optional[Dict]:
        if not (_relevance_ok(req, page) and _date_supports(req, page)):
            return None
        sentence = _extract_answer_sentence(req, page["extract"])
        if not sentence:
            return None
        answer = sentence
        if req.aspect == "runner_up":
            answer = _runner_up_answer(sentence)
            if not answer:
                return None      # cannot derive the runner-up — don't mislabel
        sources.append({
            "title": page["title"], "url": page["url"],
            "date": page.get("modified") or "",
            "relevance": "article covers the requested event/entity and "
                         "states the requested fact",
        })
        return {"status": "ok", "question": req.question, "answer": answer,
                "sources": sources, "verified": True, "reason": ""}

    def _verify_page(page: Dict[str, str], entity_bound: bool = False) -> Optional[Dict]:
        """Relevance + date + fact-extraction gate. Returns the ok-result, or
        None when the page is off-topic, stale, or doesn't state the fact —
        the caller then probes the next candidate instead of settling."""
        if not (_relevance_ok(req, page) and _date_supports(req, page)):
            return None
        sentence = _extract_answer_sentence(req, page["extract"],
                                            entity_bound=entity_bound)
        if not sentence:
            return None
        if req.aspect == "runner_up":
            sentence = _runner_up_answer(sentence)
            if not sentence:
                return None          # cannot derive the runner-up — don't mislabel
        sources.append({
            "title": page["title"], "url": page["url"],
            "date": page.get("modified") or "",
            "relevance": "article covers the requested event/entity and "
                         "states the requested fact",
        })
        return {"status": "ok", "question": req.question, "answer": sentence,
                "sources": sources, "verified": True, "reason": ""}

    # Stage 1 probes encyclopedia pages for a verifiable fact. A PRICE can
    # never legally come from a static article (stage 1 would reject every
    # sentence anyway — see the extraction guard), so skip the probing
    # entirely: it only adds seconds of latency before the honest answer.
    for year in ([] if req.aspect == "price" else _year_candidates(req)):
        for title in _wiki_titles_for(req.entity, year):
            page = _fetch_page(title)
            if not page:
                continue
            got = _verify_page(page, entity_bound=True)
            if got:
                return got
    # 1b) Fallback: probe pages found via the focused query (catches entities
    #     whose answer lives on a page not named like the entity+edition).
    if req.aspect != "price":
        for title in _ranked_search_titles(req.query, req.year):
            page = _fetch_page(title)
            if page:
                got = _verify_page(page)
                if got:
                    return got

    # 2) Web search (keyed providers first via the existing tool) as backup —
    #    a top result whose title/snippet clearly contains the fact wins, but
    #    ONLY with the same relevance bar; snippets alone never become "verified".
    results = (search_fn or _search_web)(req.query, limit=5)
    # Prices: never from static encyclopedia history (blocked above), but a
    # fresh market/exchange snippet from live search MAY state the price.
    if req.aspect == "price":
        price_re = re.compile(r"(?:us\$|\$|\u20b9|\u20ac|\u00a3)\s?[\d,]+(?:\.\d+)?"
                              r"(?:\s?(?:trillion|billion|million))?")
        for r in results:
            blob = f"{r.get('title', '')} {r.get('snippet', '')}"
            m = price_re.search(blob)
            if m and _relevance_ok(req, {"title": r.get("title", ""), "extract": blob}):
                sources.append({
                    "title": r.get("title") or "market result",
                    "url": r.get("url") or "", "date": "",
                    "relevance": "market/search result states the current price",
                })
                return {"status": "ok", "question": req.question,
                        "answer": f"{req.entity} is around {m.group(0).strip()} "
                                  "according to current market results.",
                        "sources": sources, "verified": False,
                        "reason": ""}
        return {"status": "unavailable", "question": req.question,
                "answer": (f"I can't verify the current {req.entity} price without "
                           "live market data, and I won't substitute background or "
                           "guess a number."),
                "sources": [], "verified": False, "reason": "no_live_market_data"}
    for r in results:
        blob = f"{r.get('title', '')} {r.get('snippet', '')}"
        if not _relevance_ok(req, {"title": r.get("title", ""), "extract": blob}):
            continue
        sentence = _extract_answer_sentence(req, blob + ".")
        if sentence and _date_supports(req, {"extract": blob, "title": r.get("title", "")}):
            sources.append({
                "title": r.get("title") or r.get("url") or "web result",
                "url": r.get("url") or "",
                "date": "",
                "relevance": "web result states the requested fact",
            })
            return {"status": "ok", "question": req.question, "answer": sentence,
                    "sources": sources, "verified": False,   # snippet-level: lower confidence
                    "reason": ""}

    # 2b) HISTORICAL fallback to base-model knowledge (§2/§7/§12): a past-year
    #     fact is stable, so when no live/structured source verifies it the model
    #     may answer from knowledge — clearly labelled as such. CURRENT-year facts
    #     and prices never take this path (no guessing about the present).
    if req.year and req.year < now.year and req.aspect != "price":
        try:
            from backend.llm import query_llm
            kb = query_llm(
                f"Answer the question in one or two sentences using only well-"
                f"established historical knowledge. If you are not confident, reply "
                f"with exactly the word UNSURE.\nQuestion: {req.question}",
                "You are a careful factual assistant. State only facts you are "
                "confident about; otherwise reply UNSURE.",
                timeout=12,
            )
            kb = (kb or "").strip()
            if kb and kb.upper() != "UNSURE" and len(kb) < 600:
                return {"status": "ok", "question": req.question, "answer": kb,
                        "sources": [{"title": "model knowledge (historical fact)",
                                     "url": "", "date": "",
                                     "relevance": "stable historical fact from model "
                                                  "knowledge; no live source reached"}],
                        "verified": False, "reason": "model_knowledge_historical"}
        except Exception:
            pass

    # 3) Honest unavailability (§5/§6/§13): no substitution, no guess.
    if req.year and req.year == now.year:
        reason = "event_maybe_incomplete"
        hint = (f"I can't reliably verify the {req.year} {req.entity} result right "
                "now because live search is unavailable to me at the moment, and "
                "I won't substitute background or guess.")
    else:
        reason = "no_verifiable_source"
        hint = ("I can't reliably verify this right now because live search is "
                "unavailable, and I won't substitute background or guess.")
    return {"status": "unavailable", "question": req.question, "answer": hint,
            "sources": [], "verified": False, "reason": reason}


def format_current_fact(result: Dict) -> str:
    """User-facing rendering: direct answer first, then the source (§9/§10).
    Never appends generic background."""
    if result.get("status") == "ok":
        lines = [result["answer"]]
        srcs = result.get("sources") or []
        if srcs:
            lines.append("")
            src = srcs[0]
            date_note = f" (updated {src['date']})" if src.get("date") else ""
            conf = "" if result.get("verified") else \
                " — _snippet-level match, open the link to confirm_"
            if src.get("url"):
                lines.append(f"Source: [{src['title']}]({src['url']}){date_note}{conf}")
            else:
                lines.append(f"Source: {src['title']}{date_note}")
        return "\n".join(lines)
    return result.get("answer") or (
        "I can't reliably verify this right now because live search is unavailable.")
