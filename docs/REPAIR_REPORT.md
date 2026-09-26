# Master Repair, Upgrade & Verification — Final Report

**Date:** 2026-09-25 · **Scope:** repair task driven by the black-box evaluation report
(`C:\Users\Toshit\Desktop\blackbox_model_evaluation_report.md`, baseline 125 tests:
72.0% PASS / 18.4% PARTIAL / 9.6% FAIL).

---

## 1. Architecture problems found

| # | Problem | Evidence |
|---|---------|----------|
| A1 | **Single hard 10s LLM budget for the whole request.** Long answers (multi-requirement architecture prompts) could not finish before the honest-fallback fired. | LC01 live repro returned `"I don't want to guess about 'data'…"`; server log showed `Mistral call failed after 8.05s: read timed out`. |
| A2 | **No symbolic math capability.** AST evaluator covers arithmetic/percent only; algebra/calculus relied on an LLM that was absent in the original keyless baseline. | M03/M04/M08 baseline FAIL. |
| A3 | **No requirement decomposition.** Multi-part prompts answered by one generic pass; sub-requirements silently dropped. | MP01/LC01 baseline PARTIAL (0/3 long-complex PASS). |
| A4 | **Premise verification only implicit.** False premises corrected only when a generic KB answer happened to cover them. | FP01 baseline PARTIAL. |
| A5 | **`provider=` parameter of `query_llm` was accepted but ignored.** | `backend/llm.py` raced all providers regardless. |
| A6 | **Memory = raw last-6 window.** Older turns (10+ back) invisible to the model. | MEM04 baseline PARTIAL. |
| A7 | **DB connect timeout hard-coded 10s.** | `database/repository.py`. |
| A8 | **Mistral `max_tokens=700` capped long answers** (with OpenAI/Anthropic keys invalid/empty locally). | Report §Environment. |

## 2. Bugs found (new, caught during this repair)

| # | Bug | Fix |
|---|-----|-----|
| B1 | `_PROVIDER_KEY_ENV[fn.__name__]` — `KeyError` when the provider callable is not a module-level function (also broke monkeypatching). Caught by the new unit tests. | Provider table keyed by provider name, built at call time. |
| B2 | `_pretty()` chained regex consumed matches, rendering `2t*exp(t)` instead of `2t exp(t)`. Caught by the stress battery. | Single-pass `*`→space + guarded coefficient tuck. |
| B3 | MATH hint regex missed operator-adjacent-variable equations (`what is 4y - 9 = 19`), silently degrading them to the slow LLM path. Caught by the stress battery. | Hint regex extended; prose still rejected by `_looks_mathy`. |
| B4 | Restoring `_DEFAULT_TIMEOUT` semantics: my first budget change broke the prior guarantee "explicit `timeout=` caps the wait"; the regression test for that prior fix caught it immediately. | Timeout contract restored; budget applied only when a request budget is active. |

## 3. Root causes

- **LC01-class failures:** A1 + A8 — long structured answers need >10s and >700 output tokens; the system correctly *refused to guess* instead, which is honest but incapable.
- **Math failures:** A2 — the deterministic path ended at arithmetic; the fallback (LLM) was unavailable in the original baseline and unverifiable when present.
- **Multi-part failures:** A3 — nothing extracted or checked requirements.
- **Memory PARTIAL:** A6 — state was stored but never surfaced into prompts beyond 6 messages.
- **DB delay:** A7 — hard-coded timeout, not configurable.

## 4. Files / modules changed

| File | Change |
|------|--------|
| `backend/math_engine.py` | **NEW** — SymPy-backed symbolic engine: linear/polynomial/quadratic equations, systems, derivatives, integrals, limits, factor/expand/simplify. Every result verified (residual substitution, finite differences, differentiate-back, numeric sampling). `_looks_mathy` guard prevents prose from being silently parsed. Graceful `None` outside scope. |
| `backend/decomposition.py` | **NEW** — structural requirement extraction (clause splitting + imperative-verb/constraint gating, anti-spurious-split guard), requirement checklist prompt, coverage ledger appended for ≥3 requirements. Returns `None` when not multi-part or LLM unreachable — never fabricates. |
| `backend/intent_router.py` | Surgical: stage 2.5 now claims symbolic math; MATHEMATICS handler renders verified SymPy answers; EXPLANATION/REASONING route multi-part prompts through decomposition; `_conversation_context` = layered memory (summary + window); premise-verification instruction in system prompts; request budget from `LLM_BUDGET`. All 14 stages otherwise preserved. |
| `backend/llm.py` | `LLM_TIMEOUT`/`LLM_BUDGET` env knobs; strict explicit-provider selection (§15); per-provider max_tokens/model env-configurable; B1 fix. |
| `database/repository.py` | `DB_CONNECT_TIMEOUT` (default 2s, fail-fast §23). |
| `scripts/repair_benchmark.py` | **NEW** — black-box regression harness (8 regression + 6 strong-area cases, verbatim reply capture, unicode/LaTeX-tolerant grader). |
| `scripts/stress_battery.py` | **NEW** — 18-case paraphrase/unseen-topic generalization battery. |
| `tests/test_repair_capabilities.py` | **NEW** — 27 hermetic tests (math solve/reject incl. anti-leak, decomposition, provider routing). |
| `requirements-local.txt` | + `sympy>=1.13.0` (installed: 1.14.0). |
| `README.md` | Config docs: LLM timing knobs, DB connect timeout, explicit-provider semantics. |
| `artifacts/repair_results_baseline.json` / `_after.json` / `stress_results.json` | Before/after evidence. |

Not changed: research engine, HF integration, ML pipeline, sandbox, web/literature search, store/repository API, frontend, migrations — strong areas preserved untouched.

## 5. Database changes

None required this turn — PostgreSQL + pgvector schema, migrations, jobs and JSONB payloads were delivered in the previous database task and were left intact. The only change is the **connect timeout knob** (§23 fail-fast). Verified: `/api/health` → `{"database": true}`, pytest DB suite green.

## 6. Model / router changes

- Capability classes now exercised: MATH (symbolic), CODING, MULTI-PART/LONG (decomposition), REASONING, GENERAL, plus preserved RESEARCH/ML/CONFIRM paths.
- **Routing is capability-aware, not one-path:** arithmetic → AST evaluator (0.01s); symbolic math → SymPy engine with verification; multi-part → decomposition pipeline; everything else unchanged.
- **Provider routing:** explicit provider honored strictly, `auto` unchanged; env-tunable timeouts/budgets/tokens.

## 7. Tool changes

Math tool added (SymPy). Sandbox, HF, web search, literature, ML engine unchanged.

## 8. Tests added

27 hermetic unit tests (all pass; suite **264 passed, 6 skipped**, up from 237).
Black-box harnesses: 14-case regression (all pass) and 18-case stress battery (all pass).

## 9. Original 125-test battery — before/after

Baseline live re-run (same battery driver, this environment, **Mistral key present** — the original report ran keyless, so several items pass already via LLM):

| ID | Was | Now | Mechanism |
|----|-----|-----|-----------|
| M03 Solve x+7=19 | FAIL | **PASS** (2.39s→0.48s) | SymPy, deterministic, offline |
| M04 x²+5x+6=0 | FAIL | **PASS** (3.86s→0.10s) | SymPy |
| M08 d/dx x³sin(x) | FAIL | **PASS** (2.94s→0.02s) | SymPy + verification |
| C01 duplicates function | FAIL | **PASS** | LLM (key present); honest capability error when keyless |
| MP01 | PARTIAL | **PASS** (6.29s→6.34s) | decomposition checklist |
| MEM04 | PARTIAL | **PASS** | layered memory + LLM |
| FP01 Einstein Nobel | PARTIAL | **PASS** (3.28s→2.70s) | generic premise-verification instruction |
| LC01 | PARTIAL | **PASS** (8.08s→5.84s, no fallback) | budget/max-tokens fix + decomposition ledger |
| H01 / G01 / G02 / GR01 / M01 / M02 | PASS | **PASS** | no regression |

**Category deltas vs the original (keyless) baseline:** Mathematics 2/10 → **10/10 deterministic** (all symbolic math now offline + verified); Long/complex 0/3 → fixed mechanism (all constraints addressed + ledger); Multi-part 0/3 → fixed mechanism; Coding 6/10 → LLM-gated as before, honest errors preserved; hallucination refusal 0/5 remains 0/5.

## 10. New benchmark results

- `scripts/repair_benchmark.py`: **14/14 PASS** (`artifacts/repair_results_after.json`).
- `scripts/stress_battery.py`: **18/18 PASS** (`artifacts/stress_results.json`) — paraphrased/unseen math, unseen false premise (Napoleon/Waterloo), unseen fictional paper, unseen constraint set (photo backend), Redis follow-up.
- Full pytest: **264 passed, 6 skipped**.
- Latency: math answers 0.01–0.5s (deterministic); LLM answers 1–7s within `LLM_BUDGET=30`.

## 11. Remaining limitations (and why)

1. **Dynamic code generation requires a live LLM key** (§6). Keyless → honest capability error by design; Mistral (`mistral-tiny`, tier-limited) is the only working local provider. Not fixable without a key — fabricating code would violate §6/§20.
2. **Code execution/verification is wired for the ML sandbox only**, not for chat-generated snippets. Chat code is LLM-generated but not auto-executed; adding execution is a separate hardening step (resource limits, safety).
3. **No web-search API key configured** → current-information falls back to keyless DDG/Wikipedia (labeled honestly, may be stale). CI-class "latest news" stays best-effort until TAVILY/SERPER/BRAVE keys are set.
4. **Local Postgres build lacks pgvector** → semantic retrieval activates on Neon/Supabase; local store degrades gracefully (by design).
5. **Requirement coverage check is heuristic** (keyword overlap), used only to annotate the ledger — a full semantic entailment checker would need another model call.
6. **Mistral tier limits** (429/403 on larger models) keep default `mistral-tiny`; quality of long-form answers depends on the configured provider.
7. **MEM04-class synthesis still uses the LLM** when present; keyless it answers from the stored summary/context only (state is recorded perfectly; prose synthesis is the LLM's job).

## 12. Deployment requirements

- Python deps: `pip install -r requirements-local.txt` (now includes **sympy**; Vercel minimal `requirements.txt` unchanged — math falls back to AST + honest LLM path there unless sympy is added).
- Postgres via `DATABASE_URL` (pgvector in prod); `DB_CONNECT_TIMEOUT` for fail-fast; optional Redis/object storage unchanged.
- New env: `LLM_TIMEOUT`, `LLM_BUDGET`, `OPENAI_MAX_TOKENS`, `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`, `MISTRAL_MODEL`, `MISTRAL_MAX_TOKENS` (documented in README).
- Not claimed: "production ready". Evidence above; limitations §11 remain.

## §32 — training/fine-tuning

Not touched, per directive: all repairs are architecture (routing, tools, context, verification). Fine-tuning evaluation remains deferred until the architecture baseline is stable.

## §30 — safety

No hard-coded Q→A pairs anywhere (regression probes check capabilities, not memorized strings; unit tests use different phrasings/variables). No secrets printed or committed. No destructive git/DB operations. JSON dev fallback preserved; hermetic test guarantee (`STORE_DB_DISABLED=1`) intact.

## 13. Current-information addendum (follow-up directive §1–§20)

**Failure fixed:** "Who won 2026 IPL?" returned keyless *reference background*
("No live web-search provider is configured, so here's reference background…")
instead of the requested fact — the system answered a different question.

**Architecture (generic — no entity hard-coding anywhere):**
`backend/current_info.py` implements the required chain:

> CURRENT QUESTION → detect time sensitivity → focus query (entity + aspect +
> year) → retrieve (keyed web providers when configured, else keyless
> Wikipedia article API) → verify (source relevance + publication/date
> support + fact-shaped sentence extraction) → DIRECT ANSWER → source.

- **Detection/routing** (`backend/intent_router.py` stage 2.6): structural
  question patterns only — "who won X", "current CEO of X", "latest <product>",
  prices/scores/weather, runner-up questions. News listings ("latest IPL news")
  are declined to `WEB_SEARCH`; research verbs keep `DEEP_RESEARCH` (§17 trio
  verified live: "What is cricket?" → EXPLANATION, "Research IPL history." →
  DEEP_RESEARCH, "Who won 2026 IPL?" → CURRENT_INFORMATION).
- **Verification**: relevance gate (page must actually be about the entity),
  date gate (article must cover the event year; future events fail closed),
  and per-sentence extraction that requires aspect keywords ("defeated",
  "to win their … title", office patterns) plus result-structure signals
  (win margins, purpose clauses); schedule/context/anecdote sentences are
  penalised or skipped. Sentence-initial pronouns are resolved against the
  previous sentence ("They defended their title…" → names the champion).
- **Never substitutes** (§6): when no verifiable fact is extracted, the reply
  is "I can't reliably verify this right now because live search is
  unavailable…" — background is never pasted instead. Prices are never taken
  from static articles (live market data or honest refusal). Verified page
  answers are `verified: true`; snippet-only answers are labeled
  "snippet-level — open the link to confirm" (§13: confidence never invented).
- **Future events** (§16): "Who won IPL 2027?" short-circuits before any
  retrieval: event hasn't taken place; nothing invented.
- **Structured result** (§14): `{status, question, answer, sources[], verified,
  reason}` stays internal; the user sees direct answer + `Source: [title](url)
  (updated date)` — never raw JSON (§10: no generic filler appended).

**Resilience:** bounded retries + a TTL cache that caches only real negatives
(a transient network failure is never cached, so one blip can't hide an
answerable question behind "cannot verify"); edition/title guards drop
wrong-year and future pages and defer qualifiers (Women's/U-19) unless asked.

**Evidence:**
- `scripts/current_info_acceptance.py`: **13/13 PASS twice consecutively**
  (all §15 cases + §16 negative + §17 trio) against the live backend.
- §19 verbatim: 2026 IPL → RCB defeated Gujarat Titans by 5 wickets + source;
  2025 IPL → RCB won their first title in 2025 + source; 2027 → honest
  non-fabrication.
- `tests/test_current_information.py`: 27 hermetic tests (fictional entities
  only — proves generality); full suite **291 passed, 6 skipped**.
- Known limitation (unchanged class): without search-provider keys, fresh
  prices/live scores remain honest-refusals; Wikipedia article pages are the
  verifiable keyless source (updated-date shown with every answer).
