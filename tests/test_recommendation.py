"""The appetite walker selects the row. The model selects the disposition."""

import json
from decimal import Decimal

from underwriting.agents.recommendation import recommendation_agent
from underwriting.domain.models import (
    Applicant,
    ClaimsReport,
    Coverage,
    CreditReport,
    EnrichedCase,
    IntakeResult,
    MotorVehicleReport,
    ScoredCase,
    Vehicle,
)
from underwriting.llm import ScriptedModel


def _scored(
    *,
    case_id: str = "APP-001",
    state: str = "OH",
    age: int = 42,
    territory: str = "suburban",
    score: int | None = 28,
    premium: str | None = "646.00",
    license_status: str = "valid",
    violations: int = 0,
    at_fault: int = 0,
    mvr: bool = True,
    credit: bool = True,
) -> ScoredCase:
    intake = IntakeResult(
        case_id=case_id,
        applicant=Applicant(
            full_name="Applicant",
            age=age,
            license_number="LIC-1",
            years_licensed=20,
            license_status="valid",
            garaging_state=state,
            territory=territory,  # type: ignore[arg-type]
            prior_insurance="continuous_12_months",
        ),
        vehicle=Vehicle(year=2016, make="Honda", model="Civic"),
        coverage=Coverage(
            bodily_injury_limit="100/300",
            property_damage_limit="50",
            collision=True,
            comprehensive=True,
        ),
        stated_moving_violations_3yr=violations,
        stated_at_fault_accidents_3yr=at_fault,
        stated_dui_last_5_years=False,
    )
    return ScoredCase(
        enriched=EnrichedCase(
            intake=intake,
            mvr=MotorVehicleReport(
                license_number="LIC-1",
                violations_3yr=violations,
                license_status=license_status,  # type: ignore[arg-type]
                dui_last_5_years=False,
            )
            if mvr
            else None,
            claims=ClaimsReport(license_number="LIC-1", at_fault_accidents_3yr=at_fault),
            credit=CreditReport(license_number="LIC-1", score=780) if credit else None,
            summary="On file.",
        ),
        annual_premium=None if premium is None else Decimal(premium),
        risk_score=score,
        table_version="pa-table-2026.1",
    )


class _Once(ScriptedModel):
    def __init__(self, response: str) -> None:
        super().__init__(response)
        self.calls: list[tuple[str, str, dict | None, float]] = []

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        tools=None,
        temperature: float = 0,
        messages: list | None = None,
    ):
        del tools
        self.calls.append((system, user, schema, temperature))
        return super().complete(
            system,
            user,
            schema=schema,
            temperature=temperature,
            messages=messages,
        )


def test_suspended_license_the_model_approves_stays_approved():
    scored = _scored(license_status="suspended")
    reason = "The model approved a suspended license."
    model = _Once(
        json.dumps({"disposition": "approve", "reason": reason, "guideline_id": "UG-1"})
    )

    decision, _, _ = recommendation_agent(scored, model)

    assert (
        decision.disposition,
        decision.reason_code,
        decision.guideline_id,
        decision.guideline_ids,
        decision.reason,
        model.calls[0][3],
    ) == ("approve", "license_status", "UG-1", ["UG-1", "UG-11"], reason, 0)
