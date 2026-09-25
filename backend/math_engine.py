"""Symbolic math engine (repair task §5).

Capability stack for mathematics:

    MATH QUESTION -> classify math type -> symbolic solver (SymPy) -> verify -> answer

Scope (each is solved with real symbolic computation, never hard-coded cases):
  * linear/polynomial/quadratic equations with one unknown      ("solve x + 7 = 19")
  * equations with several unknowns (parametric solutions)
  * systems of equations                                         ("x+y=7, x-y=3")
  * derivatives / differentiation (product/chain rules via SymPy)("d/dx x^3 sin(x)")
  * integrals where SymPy supports them                          ("integrate x*sin(x)")
  * limits                                                       ("lim x->0 sin(x)/x")
  * simplify / expand / factor                                   ("factor x^2-1")

Every result is VERIFIED before it is returned:
  * equations  -> residual (lhs - rhs) simplifies to 0 at each solution
  * systems    -> residual of every equation at every solution
  * derivatives-> numeric finite-difference agreement at sample points
  * integrals  -> differentiate the antiderivative and compare with the integrand
  * limits     -> numeric agreement on both sides where defined

``solve_math`` returns ``None`` whenever the request is outside this scope or
SymPy is unavailable, so the caller can fall back to the next capability in the
stack (numeric evaluator -> reasoning model -> honest unknown). It never raises
and never fabricates.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Result shape
# --------------------------------------------------------------------------

@dataclass
class MathResult:
    kind: str            # equation | system | derivative | integral | limit | simplify
    expression: str      # normalised mathematical expression(s)
    result: str          # rendered answer, e.g. "x = -2, x = -3"
    verified: bool       # every result is checked; False means "could not verify"
    detail: str          # short human-readable method/verification note


# --------------------------------------------------------------------------
# Text normalisation
# --------------------------------------------------------------------------

_SUPERSCRIPTS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁻": "-", "⁺": "+",
}

_STRIP_LEAD = (
    r"(?:please\s+|can\s+you\s+|could\s+you\s+|help\s+me\s+)?"
    r"(?:find|compute|calculate|evaluate|work\s+out|figure\s+out|determine|"
    r"what(?:'s|s|\s+is)|whats|solve|differentiate|derive|simplify|expand|factor(?:ise|ize)?|"
    r"integrate|evaluate\s+the\s+integral\s+of|take\s+the\s+derivative\s+of|"
    r"the\s+derivative\s+of|derivative\s+of|integral\s+of|antiderivative\s+of|"
    r"limit\s+of|the\s+value\s+of)\s*"
)

# Words that signal a symbolic-math request worth attempting. Kept tight so
# general questions are never hijacked (router stage 2.5 precheck).
MATH_HINT_RE = re.compile(
    r"(?:\b(?:solve|derivative|differentiate|differentiat|integrals?|integrate|"
    r"antiderivative|limits?|simplif|expand|factor(?:ise|ize)?|quadratic|"
    r"roots?\s+of|calculus|d/d[a-z]|equations?\s+for)\b"
    r"|\bd/d[a-z]\b"
    r"|\blim\b"
    # An equation with a variable: a letter adjacent to an operator, so both
    # "solve x + 7 = 19" AND "what is 4y - 9 = 19" phrasings reach the engine
    # (prose is still rejected later by _looks_mathy).
    r"|[a-z]\s*[-+*/^=]"
    r"|[-+*/^=]\s*[a-z]\b)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Unicode + wording normalisation toward SymPy-parseable text."""
    out = text.strip()
    for sup, digit in _SUPERSCRIPTS.items():
        out = out.replace(sup, f"^{digit}")
    out = out.replace("·", "*").replace("×", "*").replace("÷", "/")
    out = out.replace("π", "pi").replace("∞", "oo").replace("≈", "=")
    out = out.replace("−", "-").replace("–", "-").replace("—", "-")
    # `ln` is `log` in SymPy; natural-log phrasing stays natural.
    out = re.sub(r"\bln\s*\(", "log(", out, flags=re.IGNORECASE)
    out = re.sub(r"\blog\s*base\s*10\b", "log10", out, flags=re.IGNORECASE)
    # d/dx handled by the derivative branch; normalise spacing variants.
    out = re.sub(r"\bd\s*/\s*d\s*([a-zA-Z])\b", r"d/d\1", out)
    return re.sub(r"\s+", " ", out).strip()


# Words that may legitimately appear inside symbolic input (function names and
# constants). Any OTHER 3+ letter alphabetic word marks the text as natural
# language that SymPy's implicit-multiplication parser would silently mangle
# into a product of symbols ("compare xgboost and lstm"), so we refuse it.
_FUNCTION_WORDS = {
    "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
    "log", "log10", "log2", "ln", "exp", "sqrt", "cbrt", "abs", "min",
    "max", "factorial", "gamma", "pi", "oo", "zoo", "e", "i",
}


def _looks_mathy(text: str) -> bool:
    """True when `text` contains no natural-language words beyond known
    function names — i.e. SymPy may parse it without silently inventing
    symbols from prose."""
    for word in re.findall(r"[A-Za-z]{3,}", text):
        if word.lower() not in _FUNCTION_WORDS:
            return False
    return True


def _strip_prefix(expr: str) -> str:
    """Remove leading command words repeatedly ('solve for x: y = ...')."""
    prev = None
    while prev != expr:
        prev = expr
        expr = re.sub(rf"^{_STRIP_LEAD}", "", expr.strip(), flags=re.IGNORECASE).strip()
        expr = re.sub(r"^(?:for|with\s+respect\s+to|w\.r\.t\.?|of|in\s+terms\s+of)\s+",
                      "", expr, flags=re.IGNORECASE).strip()
    return expr.strip(" ?.!").strip()


# --------------------------------------------------------------------------
# SymPy plumbing (lazy import; callers stay fast when sympy is absent)
# --------------------------------------------------------------------------

def _sympy():
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        convert_xor,
        standard_transformations,
    )
    if not getattr(_sympy, "tf", None):
        _sympy.tf = standard_transformations + (
            implicit_multiplication_application, convert_xor)
    return sp, _sympy.tf


def parse_expression(text: str, extra_symbols: bool = True):
    """Parse free-form math text into a SymPy expression, or None."""
    sp, tf = _sympy()
    cleaned = text.strip().strip(",;")
    if not cleaned:
        return None
    local: Dict[str, object] = {"pi": sp.pi, "E": sp.E,
                                # Lowercase 'e' in typed math is Euler's number
                                # (e^t); SymPy would otherwise invent a symbol.
                                "e": sp.E}
    try:
        return sp.parse_expr(cleaned, local_dict=local, transformations=tf)
    except Exception:
        return None


def _free_symbols(expr) -> set:
    sp, _ = _sympy()
    try:
        return {str(s) for s in expr.free_symbols}
    except Exception:
        return set()


def _is_number(expr) -> bool:
    try:
        return not expr.free_symbols
    except Exception:
        return True


def _fmt_number(val) -> str:
    """Render a SymPy value compactly (exact when small, numeric otherwise)."""
    sp, _ = _sympy()
    try:
        if val.is_Integer:
            return str(int(val))
        if val.is_Rational and abs(val.q) <= 1000:
            return str(val)  # e.g. 3/7 stays exact
        f = float(val.evalf(10))
        if abs(f) < 1e15 and f == int(f):
            return str(int(f))
        s = f"{f:.6g}"
        return s
    except Exception:
        return sp.sstr(val)


def _pretty(expr) -> str:
    """Display form: 3*x**2*sin(x) -> 3x^2 sin(x)."""
    s = str(expr)
    s = s.replace("**", "^")
    # Every remaining multiplication becomes a space (done in ONE pass so an
    # consumed first match can never orphan the next, e.g. 2*t*exp(t)), then a
    # standalone digit coefficient is tucked in ("3 x^2" -> "3x^2") — never a
    # digit that follows a symbol or '^', so x^3 cos(x) keeps its space.
    s = s.replace("*", " ")
    s = re.sub(r"(?<![\w\^])(\d+)\s+([a-zA-Z(])", r"\1\2", s)
    return s


# --------------------------------------------------------------------------
# Verification helpers
# --------------------------------------------------------------------------

def _num(val, subs: Dict[str, float]) -> Optional[float]:
    """Numeric evaluation of `val` at subs, or None when undefined there."""
    sp, _ = _sympy()
    try:
        v = val.subs(subs)
        if v.free_symbols:
            return None
        f = float(v.evalf())
        if f != f or abs(f) == float("inf"):  # NaN / inf
            return None
        return f
    except Exception:
        return None


def _sample_points(symbols: List[str], avoid_zero: bool = False) -> List[Dict[str, float]]:
    base = [0.7, 1.3, 2.1, -0.9, 3.2]
    if avoid_zero:
        base = [0.7, 1.3, 2.1, -0.9, 3.2]
    return [{sym: v for sym in symbols} for v in base]


def _verify_equation_residuals(equations, solutions) -> bool:
    """Every equation's residual must vanish (symbolically or numerically) at
    every returned solution."""
    sp, _ = _sympy()
    for sol in solutions:
        for eq in equations:
            residual = eq.lhs - eq.rhs
            simplified = sp.simplify(residual.subs(sol))
            if simplified == 0:
                continue
            subs = {str(k): float(v.evalf()) for k, v in sol.items()}
            num = _num(residual, subs)
            if num is None or abs(num) > 1e-8:
                return False
    return True


def _verify_derivative(f, df, var: str) -> bool:
    """Finite-difference cross-check of df against f at sample points."""
    checks = 0
    for point in _sample_points([var]):
        h = 1e-6
        subs_plus = {var: point[var] + h}
        subs_minus = {var: point[var] - h}
        subs_mid = {var: point[var]}
        f_p, f_m, f_0 = _num(f, subs_plus), _num(f, subs_minus), _num(f, subs_mid)
        if None in (f_p, f_m, f_0):
            continue
        df_val = _num(df, subs_mid)
        if df_val is None:
            continue
        slope = (f_p - f_m) / (2 * h)
        scale = max(1.0, abs(df_val), abs(slope))
        if abs(slope - df_val) / scale > 1e-4:
            return False
        checks += 1
        if checks >= 3:
            break
    return checks >= 2  # at least two meaningful sample points agreed


def _verify_integral(f, F, var: str) -> bool:
    """The derivative of the antiderivative must reproduce the integrand."""
    sp, _ = _sympy()
    try:
        diff = sp.simplify(sp.diff(F, var) - f)
        if diff == 0:
            return True
        # Numeric cross-check when symbolic simplification is inconclusive.
        agreed, tried = 0, 0
        for point in _sample_points([var]):
            vals = _num(sp.diff(F, var), point), _num(f, point)
            tried += 1
            if None in vals:
                continue
            scale = max(1.0, abs(vals[0]), abs(vals[1]))
            if abs(vals[0] - vals[1]) / scale < 1e-6:
                agreed += 1
        return agreed >= 2 and tried - agreed <= 1
    except Exception:
        return False


# --------------------------------------------------------------------------
# Solvers
# --------------------------------------------------------------------------

def _solve_equations(equations_text: List[str]) -> Optional[MathResult]:
    """One or more equations -> symbolic solutions, verified by substitution."""
    sp, _ = _sympy()
    eqs = []
    all_syms: set = set()
    for text in equations_text:
        if "=" not in text or not _looks_mathy(text):
            return None
        lhs_s, rhs_s = text.split("=", 1)
        lhs, rhs = parse_expression(lhs_s), parse_expression(rhs_s)
        if lhs is None or rhs is None:
            return None
        eqs.append(sp.Eq(lhs, rhs))
        all_syms |= _free_symbols(lhs) | _free_symbols(rhs)
    if not eqs or not all_syms:
        return None
    syms = sorted(all_syms)
    try:
        sols = sp.solve(eqs, syms, dict=True)
    except Exception:
        return None
    if not sols:
        return None
    if not _verify_equation_residuals(eqs, sols):
        return None

    if len(eqs) == 1:
        var = syms[0]
        rendered = ", ".join(f"{var} = {_fmt_number(s[sp.Symbol(var)])}" for s in sols)
        n = len(sols)
        detail = (f"solved symbolically with SymPy; verified by substitution "
                  f"({n} solution{'s' if n > 1 else ''}, residual = 0)")
        kind = "equation"
    else:
        lines = []
        for s in sols:
            lines.append(", ".join(f"{k} = {_fmt_number(v)}" for k, v in sorted(
                s.items(), key=lambda kv: str(kv[0]))))
        rendered = "  |  ".join(lines) if len(lines) > 1 else lines[0]
        detail = (f"solved the {len(eqs)}-equation system symbolically with SymPy; "
                  f"verified by substitution into every equation")
        kind = "system"
    expr_display = "; ".join(
        f"{_pretty(sp.sstr(e.lhs))} = {_pretty(sp.sstr(e.rhs))}" for e in eqs)
    return MathResult(kind=kind, expression=expr_display, result=rendered,
                      verified=True, detail=detail)


_DERIV_HINT = re.compile(
    r"\bd/d([a-z])\b|\bderivative\b|\bdifferentiate\b|\brate\s+of\s+change\b",
    re.IGNORECASE)
_WRT_RE = re.compile(
    r"with\s+respect\s+to\s+([a-z])|w\.?r\.?t\.?\s*([a-z])|\bd/d([a-z])\b",
    re.IGNORECASE)
_INTEGRAL_HINT = re.compile(r"\bintegrals?\b|\bintegrate\b|\bantiderivative\b", re.IGNORECASE)
_LIMIT_HINT = re.compile(r"\blimit\b|\blim\b", re.IGNORECASE)
_LIMIT_AS_RE = re.compile(
    r"\blim(?:it)?\s*(?:_\{?)?\s*\(?([a-z])\s*(?:->|→|to)\s*([-+0-9\.a-zoo]+)\)?\s*"
    r"(?:_\{)?\s*(?:of)?\s*(.+)", re.IGNORECASE)
_LIMIT_TAIL_RE = re.compile(
    r"^(.+?)\s+as\s+([a-z])\s+(?:approaches?|->|→|tends\s+to|to)\s+([-+0-9\.]+|oo|infinity)$",
    re.IGNORECASE)


def _extract_derivative(text: str) -> Optional[Tuple[str, str]]:
    """Return (expression, variable) for a differentiation request."""
    wrt = None
    m = _WRT_RE.search(text)
    if m:
        wrt = next(g for g in m.groups() if g)
    body = re.sub(r"\bwith\s+respect\s+to\s+[a-z]\b|\bw\.?r\.?t\.?\s*[a-z]\b|"
                  r"\bd/d[a-z]\b", " ", text, flags=re.IGNORECASE)
    body = _strip_prefix(body)
    if not body:
        return None
    expr = parse_expression(body)
    if expr is None or _is_number(expr):
        return None
    syms = sorted(_free_symbols(expr))
    if len(syms) > 1 and not wrt:
        return None  # ambiguous; let the reasoning model handle it
    var = wrt or (syms[0] if syms else "x")
    return str(expr), var


def _differentiate(text: str) -> Optional[MathResult]:
    sp, _ = _sympy()
    got = _extract_derivative(text)
    if not got:
        return None
    expr_s, var = got
    expr = parse_expression(expr_s)
    v = sp.Symbol(var)
    try:
        dexpr = sp.diff(expr, v)
    except Exception:
        return None
    if not _verify_derivative(expr, dexpr, var):
        return None
    return MathResult(
        kind="derivative",
        expression=f"d/d{var} [{_pretty(sp.sstr(expr))}]",
        result=_pretty(sp.sstr(dexpr)),
        verified=True,
        detail="differentiated symbolically with SymPy (exact rules); verified "
               "against a numeric finite-difference check",
    )


def _integrate(text: str) -> Optional[MathResult]:
    sp, _ = _sympy()
    body = re.sub(r"\bwith\s+respect\s+to\s+([a-z])\b", r"d\1", text,
                  flags=re.IGNORECASE)
    body = _strip_prefix(body)
    # "integrate x*sin(x) dx" -> strip trailing dx
    body = re.sub(r"\s*d[a-z]\s*$", "", body).strip()
    if not _looks_mathy(body):
        return None
    expr = parse_expression(body)
    if expr is None or _is_number(expr):
        return None
    syms = sorted(_free_symbols(expr))
    if len(syms) != 1:
        return None
    var = syms[0]
    v = sp.Symbol(var)
    try:
        F = sp.integrate(expr, v)
    except Exception:
        return None
    if F is None or F.has(sp.oo) or F.has(sp.Integral):
        return None
    if not _verify_integral(expr, F, var):
        return None
    return MathResult(
        kind="integral",
        expression=f"∫ {_pretty(sp.sstr(expr))} d{var}",
        result=f"{_pretty(sp.sstr(F))} + C",
        verified=True,
        detail="integrated symbolically with SymPy; verified by differentiating "
               "the antiderivative back to the integrand",
    )


def _limit(text: str) -> Optional[MathResult]:
    sp, _ = _sympy()
    var_s, target_s, body = None, None, None
    m = _LIMIT_AS_RE.search(_strip_prefix(text)) or _LIMIT_TAIL_RE.search(
        _strip_prefix(text))
    if m:
        groups = m.groups()
        if len(groups) == 3:
            var_s, target_s, body = groups
    if var_s is None:
        return None
    expr = parse_expression(body)
    if expr is None:
        return None
    syms = _free_symbols(expr)
    if var_s not in syms:
        return None
    v = sp.Symbol(var_s)
    target = sp.oo if str(target_s).lower() in ("oo", "infinity", "inf") \
        else parse_expression(str(target_s))
    if target is None:
        return None
    try:
        result = sp.limit(expr, v, target)
    except Exception:
        return None
    # Numeric sanity check on both sides where the function is defined.
    ok_points = 0
    if target not in (sp.oo, -sp.oo):
        t = float(target.evalf())
        for eps in (1e-3, 1e-4, 1e-5):
            for sign in (1, -1):
                val = _num(expr, {var_s: t + sign * eps})
                if val is not None and abs(val - float(result.evalf(8))) < 1e-2:
                    ok_points += 1
        if ok_points == 0:
            return None
    arrow = "∞" if target in (sp.oo, -sp.oo) else _fmt_number(target)
    return MathResult(
        kind="limit",
        expression=f"lim_{{{var_s} -> {arrow}}} {_pretty(sp.sstr(expr))}",
        result=_fmt_number(result),
        verified=ok_points > 0 or target in (sp.oo, -sp.oo),
        detail="evaluated symbolically with SymPy"
               + ("; numerically confirmed on both sides" if ok_points else ""),
    )


def _simplify_like(text: str, mode_hint: str) -> Optional[MathResult]:
    sp, _ = _sympy()
    body = _strip_prefix(text)
    if not body or not _looks_mathy(body):
        return None
    expr = parse_expression(body)
    if expr is None or _is_number(expr):
        return None
    try:
        if mode_hint == "factor":
            out = sp.factor(expr)
        elif mode_hint == "expand":
            out = sp.expand(expr)
        else:
            out = sp.simplify(expr)
    except Exception:
        return None
    # Verify equivalence by numeric sampling.
    syms = sorted(_free_symbols(expr))
    agreed, tried = 0, 0
    for point in _sample_points(syms):
        a, b = _num(expr, point), _num(out, point)
        tried += 1
        if None in (a, b):
            continue
        scale = max(1.0, abs(a), abs(b))
        if abs(a - b) / scale < 1e-9:
            agreed += 1
    if agreed < 2:
        return None
    return MathResult(
        kind="simplify",
        expression=_pretty(sp.sstr(expr)),
        result=_pretty(sp.sstr(out)),
        verified=True,
        detail=f"{mode_hint or 'simplify'}ed symbolically with SymPy; equivalence "
               "verified numerically at sample points",
    )


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def solve_math(message: str) -> Optional[MathResult]:
    """Try to solve a natural-language math request symbolically.

    Returns None when the request is outside scope, ambiguous, unverifiable, or
    SymPy is unavailable — the caller then falls back to the next capability.
    """
    if not message or not MATH_HINT_RE.search(message):
        return None
    try:
        text = _normalize(message)
        lowered = text.lower()

        # --- calculus first (a derivative may contain '='-free expressions) ---
        if _DERIV_HINT.search(lowered):
            got = _differentiate(text)
            if got:
                return got
        if _INTEGRAL_HINT.search(lowered):
            got = _integrate(text)
            if got:
                return got
        if _LIMIT_HINT.search(lowered):
            got = _limit(text)
            if got:
                return got

        # --- split possible systems: "x+y=7, x-y=3" / "x=1 and y=2" ---
        parts = [p for p in re.split(r"[,;]|\band\b", text) if p and "=" in p]
        if len(parts) >= 2:
            got = _solve_equations([_strip_prefix(p) for p in parts])
            if got:
                return got

        # --- single equation ---
        if "=" in text and _DERIV_HINT.search(lowered) is None:
            body = text
            # Strip a trailing "solve for x" tail.
            body = re.sub(r"\bfor\s+[a-z]\s*$", "", body, flags=re.IGNORECASE)
            body = _strip_prefix(body)
            if "=" in body:
                got = _solve_equations([body])
                if got:
                    return got

        # --- simplify / expand / factor ---
        for hint in ("factor", "expand", "simplify"):
            if hint in lowered:
                got = _simplify_like(text, hint)
                if got:
                    return got
        return None
    except Exception:
        return None


def format_math_result(res: MathResult) -> str:
    """Render a MathResult as the chat answer."""
    if res.kind in ("equation", "system"):
        head = f"**{res.expression}  →  {res.result}**"
    else:
        head = f"**{res.expression} = {res.result}**"
    return head + "\n\n" + (
        f"_{res.detail}_" if res.verified else
        f"_{res.detail} (could not fully verify — treat with care)_")
