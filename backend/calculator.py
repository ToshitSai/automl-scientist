"""Safe arithmetic / math evaluation tool.

Implements the router's "Calculation -> calculator/Python" branch: a strict,
AST-whitelisted evaluator (stdlib only — arbitrary code is never executed).
Anything it cannot confidently evaluate returns ``None`` so the intent router
falls through to the next mode instead of guessing a number.
"""
import ast
import math
import re
from typing import Any, Dict, Optional

_ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "cbrt": lambda x: math.copysign(abs(x) ** (1.0 / 3.0), x),
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "ln": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
}
_ALLOWED_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}

_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)

# "calculate X", "what is X", "how much is X", ...
_CALC_PREFIX_RE = re.compile(
    r"^\s*(?:calculate|compute|evaluate|solve|what(?:'s|\s+is|\s+are)|whats|how\s+much\s+is|how\s+many\s+is)\b(.*)$",
    re.IGNORECASE | re.DOTALL,
)
# "15% of 240" / "15 percent of 240"
_PERCENT_OF_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
# A candidate expression: numbers, operators, parens, and letters (function
# names like sqrt/log and constants pi/e). Letters alone are NOT enough to
# evaluate — ast.parse plus the whitelist below rejects every non-numeric node,
# so word problems and unknown names fall through to the reasoning path.
_PLAIN_EXPR_RE = re.compile(r"^[\w\s+\-*/().,%^\u00d7\u00f7\u03c0]+$", re.UNICODE)

_MAX_RESULT_MAGNITUDE = 1e100  # refuse astronomically large results


def _normalize(text: str) -> str:
    t = text.strip()
    # Word-form arithmetic ("2 plus 3", "3 times 4", "5 to the power of 2").
    t = re.sub(r"\bplus\b", "+", t, flags=re.IGNORECASE)
    t = re.sub(r"\bminus\b", "-", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:times|multiplied\s+by)\b", "*", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:divided\s+by|over)\b", "/", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:to\s+the\s+power\s+of|power)\b", "**", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:modulo|mod)\b", "%", t, flags=re.IGNORECASE)
    t = t.replace("\u00d7", "*").replace("\u00f7", "/").replace("^", "**").replace("\u03c0", "pi")
    return t.strip()


def _eval_node(node) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, _BIN_OPS):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        # Pow: guard against exponent blowups (e.g. 9**9**9**9).
        if abs(right) > 1000:
            raise ValueError("exponent too large")
        if left != 0 and abs(left) > 1 and abs(right) * math.log10(abs(left)) > 100:
            raise ValueError("result too large")
        return left ** right
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_node(node.operand)
        return +value if isinstance(node.op, ast.UAdd) else -value
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _ALLOWED_FUNCS and not node.keywords):
        args = [_eval_node(a) for a in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)
    if isinstance(node, ast.Name) and node.id in _ALLOWED_CONSTS:
        return _ALLOWED_CONSTS[node.id]
    raise ValueError("disallowed expression")


def _format_number(value) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    value = float(value)
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(round(value, 10))


def try_evaluate(message: str) -> Optional[Dict[str, Any]]:
    """Evaluate an arithmetic request from natural language.

    Returns ``{"expression": ..., "value": ..., "formatted": ...}`` when the
    message is a plain calculation the strict evaluator can do, else ``None``.
    Equations ("3x+5=20"), word problems, and anything with non-arithmetic
    tokens return ``None`` — the router then uses the reasoning/LLM path and
    never invents a numeric result.
    """
    raw = (message or "").strip()
    if not raw:
        return None

    has_percent_of = bool(_PERCENT_OF_RE.search(raw))
    if "=" in raw and not has_percent_of:
        return None  # equations/assignments are not plain arithmetic here

    display = raw.rstrip("?").strip()
    expr = raw
    prefix = _CALC_PREFIX_RE.match(raw)
    if prefix:
        expr = prefix.group(1)
        display = display[len(raw) - len(expr):].strip() if len(expr) < len(raw) else display

    expr = _normalize(expr)
    expr = _PERCENT_OF_RE.sub(lambda m: f"(({m.group(1)}/100)*{m.group(2)})", expr)
    expr = expr.strip().rstrip("?=").strip()
    display = display.strip().rstrip("?=").strip() or expr

    if not expr or not _PLAIN_EXPR_RE.match(expr):
        return None
    if not any(ch.isdigit() for ch in expr):
        return None
    # A bare number ("what is 42") is not a calculation request.
    if not any(op in expr for op in "+-*/%") and "(" not in expr:
        return None

    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval_node(tree)
    except Exception:
        return None

    if isinstance(value, complex) or value is None or not math.isfinite(value):
        return None

    return {"expression": display, "value": value, "formatted": _format_number(value)}
