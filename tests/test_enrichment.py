"""Enrichment returns a validated EnrichedCase. Counts come from the tools."""

import json

from underwriting.agents.enrichment import enrichment_agent
from underwriting.domain.models import Applicant, Coverage, EnrichedCase, IntakeResult, Vehicle
from underwriting.llm import ScriptedModel
from underwriting.tools.reports import lookup_claims, lookup_credit, lookup_mvr

_SUMMARY = "Maria has two recent violations."


def _maria() -> IntakeResult:
    return IntakeResult(
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


class _Once(ScriptedModel):
    def __init__(self, response: str) -> None:
        super().__init__(response)
        self.calls: list[tuple[str, str, dict | None]] = []

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
        self.calls.append((system, user, schema))
        return super().complete(
            system,
            user,
            schema=schema,
            tools=tools,
            temperature=temperature,
            messages=messages,
        )


def test_enrichment_keeps_tool_reports_on_the_validated_case():
    intake = _maria()
    reply = json.dumps(
        {
            "intake": intake.model_dump(mode="json"),
            "mvr": {
                "license_number": "OH-10001",
                "violations_3yr": 2,
                "license_status": "valid",
                "dui_last_5_years": False,
            },
            "claims": {"license_number": "OH-10001", "at_fault_accidents_3yr": 1},
            "credit": {"license_number": "OH-10001", "score": 500},
            "summary": _SUMMARY,
        }
    )
    model = _Once(reply)

    result, input_tokens, output_tokens = enrichment_agent(intake, model)
    system, user, schema = model.calls[0]
    mvr = lookup_mvr("OH-10001")
    claims = lookup_claims("OH-10001")
    credit = lookup_credit("OH-10001")

    assert (result, json.loads(user), schema, len(model.calls), input_tokens, output_tokens) == (
        EnrichedCase(intake=intake, mvr=mvr, claims=claims, credit=credit, summary=_SUMMARY),
        {
            "intake": intake.model_dump(mode="json"),
            "mvr": None if mvr is None else mvr.model_dump(mode="json"),
            "claims": None if claims is None else claims.model_dump(mode="json"),
            "credit": None if credit is None else credit.model_dump(mode="json"),
        },
        EnrichedCase.model_json_schema(),
        1,
        len(system + user) // 4,
        len(reply) // 4,
    )
