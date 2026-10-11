"""The message chain composes, and a span records a failed call without dropping it."""

import pytest
from pydantic import ValidationError

from underwriting.domain.models import (
    Applicant,
    ClaimsReport,
    Coverage,
    Decision,
    EnrichedCase,
    IntakeResult,
    MotorVehicleReport,
    ScoredCase,
    Vehicle,
)
from underwriting.tracing import append_span


def _intake() -> IntakeResult:
    return IntakeResult(
        case_id="APP-001",
        applicant=Applicant(
            full_name="Maria Chen",
            age=42,
            license_number="OH-001",
            years_licensed=20,
            license_status="valid",
            garaging_state="OH",
            territory="suburban",
            prior_insurance="continuous_12_months",
        ),
        vehicle=Vehicle(year=2016, make="Honda", model="Civic"),
        coverage=Coverage(
            bodily_injury_limit="100/300",
            property_damage_limit="50",
            collision=True,
            comprehensive=True,
        ),
        stated_moving_violations_3yr=0,
        stated_at_fault_accidents_3yr=0,
        stated_dui_last_5_years=False,
    )


def test_later_message_nests_earlier_message_without_rewriting_it():
    intake = _intake()
    enriched = EnrichedCase(
        intake=intake,
        mvr=MotorVehicleReport(
            license_number="OH-001",
            violations_3yr=0,
            license_status="valid",
            dui_last_5_years=False,
        ),
        claims=ClaimsReport(license_number="OH-001", at_fault_accidents_3yr=0),
        credit=None,
        summary="Clean record.",
    )
    scored = ScoredCase(enriched=enriched, explanation="Pending the rating tool.")
    decision = Decision(
        case_id=intake.case_id,
        scored=scored,
        disposition="approve",
        reason_code="within_appetite",
        reason="Within appetite.",
    )

    assert decision.scored is not None
    assert decision.scored.enriched.intake == intake
    assert decision.scored.enriched.intake.applicant.full_name == "Maria Chen"
    with pytest.raises(ValidationError):
        intake.applicant.age = 22  # type: ignore[misc]


def test_timeout_span_is_kept_and_the_error_propagates():
    spans = []

    def boom():
        raise TimeoutError("scoring model")

    with pytest.raises(TimeoutError):
        append_span(
            spans,
            case_id="APP-TIMEOUT",
            agent="risk_scoring",
            received={"case_id": "APP-TIMEOUT"},
            call=boom,
        )

    assert len(spans) == 1
    assert spans[0].agent == "risk_scoring"
    assert spans[0].error == "TimeoutError"
    assert spans[0].produced is None
    assert spans[0].cost_usd == 0
