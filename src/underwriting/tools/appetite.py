"""Every matching appetite row is returned. Predicates live in the YAML, not here."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from underwriting.domain.models import Disposition, ReasonCode, ScoredCase

_TABLE_PATH = Path(__file__).resolve().parents[1] / "tables" / "appetite.yaml"


@dataclass(frozen=True)
class AppetiteRow:
    """One matching appetite row and the decision that row records."""

    id: str
    reason_code: ReasonCode
    guidance: str
    decision: Disposition


@dataclass(frozen=True)
class _Guide:
    """The parsed appetite file."""

    written_states: frozenset[str]
    rows: tuple[dict[str, Any], ...]


@lru_cache
def _guide() -> _Guide:
    """Load the appetite file once."""
    document = yaml.safe_load(_TABLE_PATH.read_text(encoding="utf-8"))
    return _Guide(
        written_states=frozenset(document["written_states"]),
        rows=tuple(document["rows"]),
    )


def _stated_count(value: int | None) -> int:
    """Return a stated count, using 0 when the application left it blank."""
    return 0 if value is None else value


def build_facts(scored: ScoredCase) -> dict[str, Any]:
    """Derive the columns the appetite table matches on.

    License, DUI, and violations come from the MVR when it is present, otherwise
    the application. The at-fault count comes from claims the same way. Credit
    below 640 is an aggravator only outside California.
    """
    guide = _guide()
    enriched = scored.enriched
    intake = enriched.intake
    applicant = intake.applicant
    mvr = enriched.mvr
    claims = enriched.claims
    state = applicant.garaging_state
    violations = mvr.violations_3yr if mvr is not None else _stated_count(
        intake.stated_moving_violations_3yr
    )
    at_fault = (
        claims.at_fault_accidents_3yr
        if claims is not None
        else _stated_count(intake.stated_at_fault_accidents_3yr)
    )
    credit_below_640 = (
        state != "CA" and enriched.credit is not None and enriched.credit.score < 640
    )
    aggravators = (
        int(violations >= 1)
        + int(at_fault >= 1)
        + int(applicant.prior_insurance in {"lapse", "none"})
        + int(credit_below_640)
    )
    credit_missing = enriched.credit is None and state != "CA"
    return {
        "license_status": mvr.license_status if mvr is not None else applicant.license_status,
        "state_written": state in guide.written_states,
        "dui": mvr.dui_last_5_years if mvr is not None else bool(intake.stated_dui_last_5_years),
        "at_fault": at_fault,
        "violations": violations,
        "reports_missing": mvr is None or claims is None or credit_missing,
        "score_missing": scored.annual_premium is None or scored.risk_score is None,
        "age": applicant.age,
        "territory": applicant.territory,
        "aggravator_count": aggravators,
        "score": scored.risk_score,
    }


def _score_matches(spec: Any, score: int | None) -> bool:
    """Return whether the score sits in the row's band. `any` matches a missing score too."""
    if spec == "any":
        return True
    if score is None:
        return False
    return spec["min"] <= score <= spec["max"]


def _clause(clause: dict[str, Any], facts: dict[str, Any]) -> bool:
    """Evaluate one predicate. `all` and `any` nest. A leaf compares one fact."""
    if "all" in clause:
        return all(_clause(item, facts) for item in clause["all"])
    if "any" in clause:
        return any(_clause(item, facts) for item in clause["any"])
    field = facts[clause["field"]]
    op = clause["op"]
    value = clause["value"]
    if op == "eq":
        return field == value
    if op == "in":
        return field in value
    if op == "lt":
        return field < value
    if op == "gte":
        return field >= value
    raise ValueError(f"unknown appetite operator {op}")


def _row_matches(row: dict[str, Any], facts: dict[str, Any]) -> bool:
    """Return whether this row's score band and predicates match the facts."""
    if not _score_matches(row["score"], facts["score"]):
        return False
    when = row.get("when")
    if when is None:
        return True
    return _clause(when, facts)


def match_appetite(scored: ScoredCase) -> tuple[AppetiteRow, ...]:
    """Return every appetite row that matches this scored case, in table order."""
    guide = _guide()
    facts = build_facts(scored)
    matched = tuple(
        AppetiteRow(
            id=row["id"],
            reason_code=row["reason_code"],
            guidance=" ".join(row["guidance"].split()),
            decision=row["decision"],
        )
        for row in guide.rows
        if _row_matches(row, facts)
    )
    if not matched:
        raise ValueError(f"no appetite row matched {scored.enriched.intake.case_id}")
    return matched
