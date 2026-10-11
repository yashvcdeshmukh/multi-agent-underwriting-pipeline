"""Scoring calls price, then keeps the model's explanation on that quote."""

import json
from decimal import Decimal

from underwriting.agents.scoring import risk_scoring_agent
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
from underwriting.llm import Completion, ToolCall
from underwriting.tools.rating import rate

_EXPLANATION = "The model priced this risk at 999 dollars."


def _maria() -> EnrichedCase:
    intake = IntakeResult(
        case_id="APP-001",
        applicant=Applicant(
            full_name="Maria Chen",
            age=42,
            license_number="OH-10001",
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
    return EnrichedCase(
        intake=intake,
        mvr=MotorVehicleReport(
            license_number="OH-10001",
            violations_3yr=0,
            license_status="valid",
            dui_last_5_years=False,
        ),
        claims=ClaimsReport(license_number="OH-10001", at_fault_accidents_3yr=0),
        credit=CreditReport(license_number="OH-10001", score=780),
        summary="Clean record.",
    )


_MARIA_ARGS = {
    "age": 42,
    "years_licensed": 20,
    "territory": "suburban",
    "prior_insurance": "continuous_12_months",
    "garaging_state": "OH",
    "vehicle_year": 2016,
    "moving_violations_3yr": 0,
    "at_fault_accidents_3yr": 0,
    "credit_score": 780,
}


class _PricesThenExplains:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, dict | None, list | None]] = []

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
        del system, user, temperature
        self.calls.append((json.dumps(messages), schema, tools))
        if tools and len(self.calls) == 1:
            return Completion("", 1, 1, (ToolCall("price", _MARIA_ARGS, id="call-1"),))
        return Completion(self.response, 2, 3)


def test_scoring_sends_the_priced_result_back_and_keeps_the_model_case():
    enriched = _maria()
    reply = json.dumps(
        {
            "enriched": enriched.model_dump(mode="json"),
            "factors": [{"name": "age", "level": "36-55", "multiplier": "1.00"}],
            "combined_factor": "0.8075",
            "annual_premium": "999.00",
            "risk_score": 1,
            "explanation": _EXPLANATION,
            "table_version": "pa-table-2026.1",
        }
    )
    model = _PricesThenExplains(reply)

    result, input_tokens, output_tokens = risk_scoring_agent(enriched, model)
    follow_up = model.calls[1][0]

    assert (
        result.enriched,
        result.annual_premium,
        result.risk_score,
        result.explanation,
        result.table_version,
        "646.00" in follow_up,
        model.calls[0][2][0]["function"]["name"],
        model.calls[1][1],
        model.calls[1][2],
        len(model.calls),
        input_tokens,
        output_tokens,
    ) == (
        enriched,
        Decimal("646.00"),
        28,
        _EXPLANATION,
        "pa-table-2026.1",
        True,
        "price",
        ScoredCase.model_json_schema(),
        None,
        2,
        3,
        4,
    )


def test_california_credit_is_not_a_rating_factor():
    enriched = _maria()
    applicant = enriched.intake.applicant.model_copy(update={"garaging_state": "CA"})
    intake = enriched.intake.model_copy(update={"applicant": applicant})
    priced = rate(intake, enriched.mvr, enriched.claims, enriched.credit)
    credit = next(factor for factor in priced.factors if factor.name == "credit")

    assert (credit.level, credit.multiplier) == ("CA", Decimal("1.00"))


def test_missing_credit_does_not_invent_a_score():
    enriched = _maria()
    priced = rate(enriched.intake, enriched.mvr, enriched.claims, None)
    credit = next(factor for factor in priced.factors if factor.name == "credit")

    assert (credit.level, credit.multiplier) == ("missing", Decimal("1.00"))

