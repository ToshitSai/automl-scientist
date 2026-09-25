"""Repair-task capability tests (math engine, decomposition, LLM routing).

Hermetic: no network, no live LLM, no real database. The math-engine cases are
PHRASED generically (different phrasings/variables than the black-box battery)
— the capability must generalise, not memorise.
"""
import os
import sys

import pytest

os.environ.setdefault("STORE_DB_DISABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import math_engine as me  # noqa: E402
from backend import decomposition as dec  # noqa: E402
from backend import llm as llm_mod  # noqa: E402

# Saved at import time, BEFORE conftest's autouse no_llm fixture stubs
# query_llm: the provider-routing tests below restore the real dispatcher
# (the provider call_* functions themselves stay stubbed, so no network).  
_REAL_QUERY_LLM = llm_mod.query_llm


@pytest.fixture
def real_query_llm(monkeypatch):
    """Restore the real query_llm dispatcher (autouse no_llm stubs it)."""
    monkeypatch.setattr(llm_mod, "query_llm", _REAL_QUERY_LLM)


# ---------------------------------------------------------------------------
# Math engine — solve (capability, not memorised answers)
# ---------------------------------------------------------------------------

class TestMathEngineSolves:
    def test_linear_equation_other_variable(self):
        r = me.solve_math("solve 4y - 9 = 19")
        assert r is not None and r.verified
        assert "7" in r.result

    def test_linear_equation_fractions(self):
        r = me.solve_math("solve 2n/3 = 8")
        assert r is not None and r.verified
        assert "12" in r.result

    def test_quadratic_two_roots(self):
        r = me.solve_math("solve t^2 - 7t + 12 = 0")
        assert r is not None and r.verified
        assert "3" in r.result and "4" in r.result

    def test_system_of_equations(self):
        r = me.solve_math("solve 3a + b = 10 and a - b = 2")
        assert r is not None and r.verified
        assert r.kind == "system"
        assert "3" in r.result and "1" in r.result

    def test_derivative_product(self):
        r = me.solve_math("differentiate z^2 cos(z)")
        assert r is not None and r.verified
        assert r.kind == "derivative"
        low = r.result.lower().replace("**", "^").replace(" ", "")
        assert "2z" in low and "cos" in low and "sin" in low

    def test_derivative_polynomial(self):
        r = me.solve_math("what is the derivative of 5u^3")
        assert r is not None and "15" in r.result

    def test_integral(self):
        r = me.solve_math("integrate 6w^2 dw")
        assert r is not None and r.verified
        assert r.kind == "integral" and "w^3" in r.result.replace("**", "^")

    def test_limit(self):
        r = me.solve_math("lim x->2 (x^2 - 4)/(x - 2)")
        assert r is not None and r.verified
        assert "4" in r.result

    def test_factor(self):
        r = me.solve_math("factor p^2 + 5p + 6")
        assert r is not None
        assert "p + 2" in r.result.replace("**", "^")

    def test_log_equation(self):
        r = me.solve_math("solve log(k) = 3")
        assert r is not None and r.verified


class TestMathEngineRejects:
    @pytest.mark.parametrize("msg", [
        "compare XGBoost and LSTM and explain the trade-offs",
        "why did Feynman win the Nobel Prize for quantum electrodynamics?",
        "tell me about photosynthesis in simple words",
        "what is the capital of Australia",
        "research the latest transformer architectures",
    ])
    def test_natural_language_not_solved(self, msg):
        assert me.solve_math(msg) is None

    def test_plain_arithmetic_left_to_calculator(self):
        # No symbolic hint words -> arithmetic belongs to the AST evaluator.
        assert me.solve_math("what is 1234 * 5678") is None


# ---------------------------------------------------------------------------
# Decomposition — requirement extraction & coverage
# ---------------------------------------------------------------------------

MP = ("Explain Rust, compare it with Go, give one example of each, and tell me "
      "which has the gentler learning curve.")


class TestDecomposition:
    def test_multi_part_detected(self):
        assert dec.is_multi_part(MP) is True

    def test_simple_question_not_multi_part(self):
        assert dec.is_multi_part("What is photosynthesis?") is False

    def test_casual_chatter_not_multi_part(self):
        m = ("Hey so I was just wondering, how has your day been, mine has been "
             "quite long, and I am rather tired, but it was still a good day overall.")
        assert dec.is_multi_part(m) is False

    def test_constraint_ledger_extracted(self):
        m = ("Design an API gateway. It must support rate limiting; requests "
             "must be authenticated with JWT tokens; keep p95 latency under "
             "50ms; explain how you would roll it out safely.")
        d = dec.extract_requirements(m)
        kinds = {r.kind for r in d.requirements}
        assert "constraint" in kinds
        assert d.complex_enough

    def test_unreachable_llm_returns_none_not_fabrication(self):
        assert dec.handle_complex(MP, lambda p, s: None) is None

    def test_reachable_llm_answer_gets_ledger(self):
        fake = lambda p, s: (  # noqa: E731
            "Section R1: Rust explained. Section R2: compared with Go. "
            "Section R3: rust example. Section R4: go example. "
            "Section R5: learning curve verdict."
        )
        out = dec.handle_complex(MP, fake)
        assert out is not None
        assert "Requirement coverage" in out

    def test_prompt_includes_requirements(self):
        captured = {}

        def fake_llm(prompt, system):
            captured["prompt"], captured["system"] = prompt, system
            return "answer"

        dec.handle_complex(MP, fake_llm)
        assert "R1." in captured["prompt"] and "R" in captured["prompt"]
        assert "EVERY requirement" in captured["prompt"]


# ---------------------------------------------------------------------------
# LLM routing — explicit provider selection (§15)
# ---------------------------------------------------------------------------

class TestExplicitProviderRouting:
    def test_explicit_provider_without_key_is_none(self, real_query_llm, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        assert llm_mod.query_llm("hi", provider="mistral") is None

    def test_explicit_provider_is_called_not_raced(self, real_query_llm, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("other providers must not be called")

        monkeypatch.setattr(llm_mod, "call_openai_api", boom)
        monkeypatch.setattr(llm_mod, "call_gemini_api", boom)
        monkeypatch.setattr(llm_mod, "call_anthropic_api", boom)
        monkeypatch.setattr(llm_mod, "call_mistral_api",
                            lambda p, s=None, t=8: "mistral says hi")
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
        out = llm_mod.query_llm("hi", provider="mistral")
        assert out == "mistral says hi"

    def test_unknown_provider_is_none(self, real_query_llm):
        assert llm_mod.query_llm("hi", provider="nonexistent") is None

    def test_budget_config_env(self):
        from backend import llm
        assert llm._DEFAULT_BUDGET >= 5.0
        assert llm._DEFAULT_TIMEOUT >= 1
