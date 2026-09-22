"""License gate for fine-tuning datasets.

Two dataset shapes are handled:

  * ``mixture`` (e.g. allenai/tulu-3-sft-mixture): the usable license is bounded
    by the MOST RESTRICTIVE component, so the top-level tag is not sufficient.
  * ``single``  (e.g. nvidia/Nemotron-Post-Training-Dataset-v2): one top-level
    license, but a per-row ``license`` field and/or gating can still constrain
    commercial use.

The gate turns these into a clear allow/block decision so a future training
backend refuses to run on data the project is not cleared to use. Pure logic —
no network, no third-party deps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import DATASET_LICENSE_PROFILES, FineTuneConfig

# Top-level licenses considered permissive (commercial-OK with attribution).
_PERMISSIVE = {"cc-by-4.0", "apache-2.0", "mit", "odc-by", "cc-by-3.0", "bsd-3-clause"}
# Top-level licenses that are non-commercial by themselves.
_NON_COMMERCIAL = {"cc-by-nc-4.0", "cc-by-nc-sa-4.0", "cc-by-nc-nd-4.0", "cc-nc", "gpl-3.0"}


@dataclass
class LicenseDecision:
    allowed: bool
    dataset: str
    intended_use: str
    blocking: List[str] = field(default_factory=list)   # must be excluded/cleared
    gated: List[str] = field(default_factory=list)      # need access approval
    unclear: List[str] = field(default_factory=list)    # no explicit license
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "dataset": self.dataset,
            "intended_use": self.intended_use,
            "blocking": self.blocking,
            "gated": self.gated,
            "unclear": self.unclear,
            "notes": self.notes,
        }


def _evaluate_mixture(config: FineTuneConfig, profile: Dict) -> LicenseDecision:
    excluded = set(config.excluded_sources)
    components = profile.get("components") or {}
    active = {k: v for k, v in components.items() if k not in excluded}

    blocking = sorted(k for k, v in active.items() if v["status"] == "non_commercial")
    gated = sorted(k for k, v in active.items() if v["status"] == "gated")
    unclear = sorted(k for k, v in active.items() if v["status"] == "unclear")

    if config.intended_use != "commercial":
        return LicenseDecision(
            allowed=True, dataset=config.dataset_repo_id, intended_use=config.intended_use,
            blocking=blocking, gated=gated, unclear=unclear,
            notes=(
                "Non-commercial/research use permitted with attribution. "
                f"{len(gated)} gated source(s) still require HF access approval."
            ),
        )

    # Gating is an ACCESS prerequisite (request approval), not a license bar:
    # a gated permissive component is commercial-OK once access is granted.
    problems = blocking + unclear
    if problems:
        return LicenseDecision(
            allowed=False, dataset=config.dataset_repo_id, intended_use=config.intended_use,
            blocking=blocking, gated=gated, unclear=unclear,
            notes=(
                "COMMERCIAL USE BLOCKED. Binding constraint = most restrictive "
                "component. Exclude or clear: " + ", ".join(problems)
                + ". The mixture's top-level ODC-By tag does NOT override a "
                "CC-BY-NC component."
                + (f" Also obtain access approval for gated: {', '.join(gated)}." if gated else "")
            ),
        )
    return LicenseDecision(
        allowed=True, dataset=config.dataset_repo_id, intended_use=config.intended_use,
        gated=gated,
        notes="All active components are commercial-safe (attribution required)."
        + (f" Obtain access approval for gated: {', '.join(gated)}." if gated else ""),
    )


def _evaluate_single(config: FineTuneConfig, profile: Dict) -> LicenseDecision:
    top = (profile.get("license") or "").lower()
    gated = [config.dataset_repo_id] if profile.get("gated") else []

    if config.intended_use != "commercial":
        notes = "Non-commercial/research use permitted with attribution."
        if profile.get("gated"):
            notes += " Dataset is gated — accept terms + provide HF_TOKEN to download."
        return LicenseDecision(
            allowed=True, dataset=config.dataset_repo_id, intended_use=config.intended_use,
            gated=gated, notes=notes,
        )

    # Commercial path.
    blocking: List[str] = []
    unclear: List[str] = []
    if top in _NON_COMMERCIAL:
        blocking.append(f"{config.dataset_repo_id} ({top})")
    elif top not in _PERMISSIVE:
        unclear.append(f"{config.dataset_repo_id} (top-level '{top or 'unknown'}')")

    # A per-row license field means individual examples can carry stricter terms
    # than the top-level tag; require an explicit audit before commercial use.
    if profile.get("per_row_license") and not config.per_row_license_audited:
        unclear.append(
            f"{config.dataset_repo_id} per-row `license` field (audit required: "
            "set per_row_license_audited=True only after verifying every row)"
        )

    # Gating is an ACCESS prerequisite, not a license bar.
    problems = blocking + unclear
    if problems:
        return LicenseDecision(
            allowed=False, dataset=config.dataset_repo_id, intended_use=config.intended_use,
            blocking=blocking, gated=gated, unclear=unclear,
            notes=(
                "COMMERCIAL USE NOT CLEARED. Top-level license is "
                f"'{profile.get('license')}', but unresolved: " + ", ".join(problems)
                + (f" Also obtain access approval (gated)." if gated else "")
            ),
        )
    return LicenseDecision(
        allowed=True, dataset=config.dataset_repo_id, intended_use=config.intended_use,
        gated=gated,
        notes="Top-level license is permissive and per-row audit is complete (attribution required)."
        + (" Obtain access approval (dataset is gated) before download." if gated else ""),
    )


def evaluate(config: FineTuneConfig) -> LicenseDecision:
    """Decide whether ``config`` is licensed for its ``intended_use``."""
    profile: Optional[Dict] = config.profile()
    if profile is None:
        return LicenseDecision(
            allowed=False, dataset=config.dataset_repo_id, intended_use=config.intended_use,
            unclear=[config.dataset_repo_id],
            notes=(
                "No license profile recorded for this dataset. Inspect its source "
                "license on the HF Hub and add a profile before any use."
            ),
        )
    if profile.get("kind") == "mixture":
        return _evaluate_mixture(config, profile)
    return _evaluate_single(config, profile)


def assert_allowed(config: FineTuneConfig) -> LicenseDecision:
    """Return the decision, or raise if the config is not licensed for use."""
    decision = evaluate(config)
    if not decision.allowed:
        raise PermissionError(decision.notes)
    return decision
