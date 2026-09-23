"""Shared pytest fixtures.

Two guarantees for every test:
  * The on-disk research store is never touched (isolated temp file + no-op save).
  * The LLM is disabled, so tests exercise the deterministic fallback logic and
    prove the bot still behaves correctly when no provider is reachable.
"""
import pytest

import database.store as store_mod
import backend.llm as llm_mod
import backend.intent_router as intent_mod


@pytest.fixture(autouse=True)
def isolate_store(tmp_path, monkeypatch):
    """Point the store singleton at a temp file, reset state, disable writes."""
    store = store_mod.store
    monkeypatch.setattr(store, "filepath", str(tmp_path / "store.json"))
    store.data = store._default_state()
    monkeypatch.setattr(store, "save", lambda *a, **k: None)
    return store


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Force every LLM call to return None (simulates unavailable/invalid keys)."""
    monkeypatch.setattr(llm_mod, "query_llm", lambda *a, **k: None)
    monkeypatch.setattr(intent_mod, "query_llm", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def no_network_tools(monkeypatch):
    """Keep the unit suite hermetic: patch the low-level search providers (not
    search_web itself) so no test touches the network, while the real provider
    selection logic stays testable. Tests can still stub higher-level layers."""
    import backend.web_search as ws
    import backend.literature_search as ls
    import backend.deep_research as dr
    for name in ("_search_tavily", "_search_serper", "_search_brave", "_search_duckduckgo"):
        monkeypatch.setattr(ws, name, lambda *a, **k: [])
    monkeypatch.setattr(ls, "search_literature", lambda *a, **k: [])
    monkeypatch.setattr(dr, "search_web", lambda *a, **k: [])
    monkeypatch.setattr(dr, "search_literature", lambda *a, **k: [])
    monkeypatch.setattr(dr, "query_llm", lambda *a, **k: None)
