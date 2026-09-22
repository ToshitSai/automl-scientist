"""License gate for the fine-tuning dataset mixture.

A mixture's usable license is bounded by its MOST RESTRICTIVE component. This
module turns the static component map (``config.MIXTURE_COMPONENT_LICENSES``)
into a clear allow/block decision so a future training backend refuses to run
on data the project is not cleared to use.

Pure logic — no network, no third-party deps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .config import MIXTURE_COMPONENT_LICENSES, FineTuneConfig


@dataclass
class LicenseDecision:
    allowed: bool
    intended_use: str
    blocking: List[str]      # sources that must be excluded/cleared
    gated: List[str]         # sources requiring access approval
    unclear: List[str]       # sources with no explicit license tag
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "intended_use": self.intended_use,
            "blocking": self.blocking,
            "gated": self.gated,
            "unclear": self.unclear,
            "notes": self.notes,
        }


def evaluate(config: FineTuneConfig) -> LicenseDecision:
    """Decide whether ``config`` is licensed for its ``intended_use``.

    Research/non-commercial use is allowed with attribution. Commercial use is
    blocked while any non-commercial, gated, or unclear-license component
    remains in the mixture (after applying ``config.excluded_sources``).
    """
    excluded = set(config.excluded_sources)
    active = {k: v for k, v in MIXTURE_COMPONENT_LICENSES.items() if k not in excluded}

    blocking = sorted(k for k, v in active.items() if v["status"] == "non_commercial")
    gated = sorted(k for k, v in active.items() if v["status"] == "gated")
    unclear = sorted(k for k, v in active.items() if v["status"] == "unclear")

    if config.intended_use != "commercial":
        return LicenseDecision(
            allowed=True,
            intended_use=config.intended_use,
            blocking=blocking,
            gated=gated,
            unclear=unclear,
            notes=(
                "Non-commercial/research use permitted with attribution. Note: "
                f"{len(gated)} gated source(s) still require HF access approval "
                "before download."
            ),
        )

    problems = blocking + gated + unclear
    if problems:
        return LicenseDecision(
            allowed=False,
            intended_use=config.intended_use,
            blocking=blocking,
            gated=gated,
            unclear=unclear,
            notes=(
                "COMMERCIAL USE BLOCKED. Binding constraint = most restrictive "
                "component. Resolve by excluding or clearing: "
                + ", ".join(problems)
                + ". The mixture's top-level ODC-By tag does NOT override a "
                "CC-BY-NC component."
            ),
        )

    return LicenseDecision(
        allowed=True,
        intended_use=config.intended_use,
        blocking=[],
        gated=[],
        unclear=[],
        notes="All active components are commercial-safe (attribution required).",
    )


def assert_allowed(config: FineTuneConfig) -> LicenseDecision:
    """Return the decision, or raise if the config is not licensed for use."""
    decision = evaluate(config)
    if not decision.allowed:
        raise PermissionError(decision.notes)
    return decision
