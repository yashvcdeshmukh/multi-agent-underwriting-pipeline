"""Intake extracts Maria Chen's application through one scripted model call."""

import json

from underwriting.agents.intake import intake_agent
from underwriting.domain.models import IntakeResult
from underwriting.fixtures.applications import raw_application
from underwriting.llm import ScriptedModel

_RESPONSE = {
    "case_id": "APP-001",
    "applicant": {
        "full_name": "Maria Chen",
        "age": 42,
        "license_number": "OH-10001",
        "years_licensed": 20,
        "license_status": "valid",
        "garaging_state": "OH",
        "territory": "suburban",
        "prior_insurance": "continuous_12_months",
    },
    "vehicle": {"year": 2016, "make": "Honda", "model": "Civic"},
    "coverage": {
        "bodily_injury_limit": "100/300",
        "property_damage_limit": "50",
        "collision": True,
        "comprehensive": True,
    },
    "missing_fields": [],
    "stated_moving_violations_3yr": 0,
    "stated_at_fault_accidents_3yr": 0,
    "stated_dui_last_5_years": False,
}


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


def test_intake_extracts_maria_chen():
    raw = raw_application("APP-001")
    reply = json.dumps(_RESPONSE)
    model = _Once(reply)

    result, input_tokens, output_tokens = intake_agent(raw, model)
    system, user, schema = model.calls[0]

    assert (result, user, schema, len(model.calls), input_tokens, output_tokens) == (
        IntakeResult.model_validate_json(reply),
        raw,
        IntakeResult.model_json_schema(),
        1,
        len(system + user) // 4,
        len(reply) // 4,
    )
