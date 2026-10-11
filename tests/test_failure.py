"""A model timeout is retried, then referred. A missing scored case refers."""

from underwriting.domain.models import (
    Applicant,
    Coverage,
    EnrichedCase,
    IntakeResult,
    ScoredCase,
    Vehicle,
)
from underwriting.fixtures.applications import raw_application
from underwriting.llm import Completion, ToolCall, complete_as
from underwriting.pipeline import underwrite

_INTAKE = IntakeResult(
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


class _Canned:
    """Answers intake and enrichment so a test can reach scoring. Not a live model."""

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        tools=None,
        temperature: float = 0,
        messages: list | None = None,
    ) -> Completion:
        del system, user, temperature, messages
        title = "" if schema is None else schema.get("title", "")
        if tools and title != "ScoredCase":
            return Completion("", 1, 1, (ToolCall("price", {}),))
        if title == "IntakeResult":
            return Completion(_INTAKE.model_dump_json(), 1, 1)
        if title == "EnrichedCase":
            text = EnrichedCase(
                intake=_INTAKE,
                mvr=None,
                claims=None,
                credit=None,
                summary="Reports attached.",
            ).model_dump_json()
            return Completion(text, 1, 1)
        raise ValueError(f"no canned reply for {title}")


class _TimeoutScoring(_Canned):
    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        tools=None,
        temperature: float = 0,
        messages: list | None = None,
    ) -> Completion:
        self.calls += 1
        if tools:
            raise TimeoutError("scoring model")
        return super().complete(
            system,
            user,
            schema=schema,
            tools=tools,
            temperature=temperature,
            messages=messages,
        )


class _SkipsRate(_Canned):
    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        tools=None,
        temperature: float = 0,
        messages: list | None = None,
    ) -> Completion:
        if tools:
            return Completion("{}", 1, 1)
        return super().complete(
            system,
            user,
            schema=schema,
            tools=tools,
            temperature=temperature,
            messages=messages,
        )


class _Flaky:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        tools=None,
        temperature: float = 0,
        messages: list | None = None,
    ) -> Completion:
        del system, user, schema, tools, temperature, messages
        self.calls += 1
        if self.calls < 3:
            raise TimeoutError("model")
        return Completion(self.response, 1, 1)


def test_complete_as_retries_timeout_then_returns_the_model():
    reply = _INTAKE.model_dump_json()
    model = _Flaky(reply)

    result, _, _ = complete_as(model, "system", "user", IntakeResult)

    assert (model.calls, result) == (3, _INTAKE)


class _TimeoutTitle(_Canned):
    def __init__(self, title: str) -> None:
        self.title = title
        self.calls = 0

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        tools=None,
        temperature: float = 0,
        messages: list | None = None,
    ) -> Completion:
        self.calls += 1
        seen = "" if schema is None else schema.get("title", "")
        if seen == self.title:
            raise TimeoutError(self.title)
        if seen == "ScoredCase":
            enriched = EnrichedCase(
                intake=_INTAKE,
                mvr=None,
                claims=None,
                credit=None,
                summary="Reports attached.",
            )
            text = ScoredCase(enriched=enriched, explanation="Priced.").model_dump_json()
            return Completion(text, 1, 1)
        if tools:
            return Completion(
                "",
                1,
                1,
                (
                    ToolCall(
                        "price",
                        {
                            "age": 42,
                            "years_licensed": 20,
                            "territory": "suburban",
                            "prior_insurance": "continuous_12_months",
                            "garaging_state": "OH",
                            "vehicle_year": 2016,
                            "moving_violations_3yr": 0,
                            "at_fault_accidents_3yr": 0,
                            "credit_score": 780,
                        },
                        id="call-1",
                    ),
                ),
            )
        return super().complete(
            system,
            user,
            schema=schema,
            tools=tools,
            temperature=temperature,
            messages=messages,
        )


def test_intake_timeout_refers_without_later_agents():
    model = _TimeoutTitle("IntakeResult")

    decision, spans = underwrite(raw_application("APP-001"), model)

    assert (
        decision.disposition,
        decision.reason_code,
        decision.reason,
        decision.scored,
        [(span.agent, span.error) for span in spans],
        model.calls,
    ) == (
        "refer",
        "intake_unavailable",
        "Intake timed out after retries.",
        None,
        [("intake", "TimeoutError")],
        3,
    )


def test_enrichment_timeout_refers_without_scoring():
    model = _TimeoutTitle("EnrichedCase")

    decision, spans = underwrite(raw_application("APP-001"), model)

    assert (
        decision.disposition,
        decision.reason_code,
        decision.reason,
        decision.scored,
        [(span.agent, span.error) for span in spans],
        model.calls,
    ) == (
        "refer",
        "enrichment_unavailable",
        "Enrichment timed out after retries.",
        None,
        [("intake", None), ("enrichment", "TimeoutError")],
        4,
    )


def test_scoring_timeout_refers_after_retries():
    model = _TimeoutScoring()

    decision, spans = underwrite(raw_application("APP-TIMEOUT"), model)

    assert (
        decision.disposition,
        decision.reason_code,
        decision.reason,
        decision.scored,
        [(span.agent, span.error) for span in spans],
        model.calls,
    ) == (
        "refer",
        "scoring_unavailable",
        "Scoring timed out after retries.",
        None,
        [
            ("intake", None),
            ("enrichment", None),
            ("risk_scoring", "TimeoutError"),
        ],
        5,
    )


def test_recommendation_timeout_refers_and_keeps_the_scored_case():
    model = _TimeoutTitle("RecommendationChoice")

    decision, spans = underwrite(raw_application("APP-001"), model)

    assert (
        decision.disposition,
        decision.reason_code,
        decision.reason,
        decision.scored is not None and decision.scored.enriched.intake.case_id,
        [(span.agent, span.error) for span in spans],
        model.calls,
    ) == (
        "refer",
        "recommendation_unavailable",
        "Recommendation timed out after retries.",
        "APP-001",
        [
            ("intake", None),
            ("enrichment", None),
            ("risk_scoring", None),
            ("recommendation", "TimeoutError"),
        ],
        7,
    )


def test_scoring_without_rate_risk_refers_without_recommendation():
    decision, spans = underwrite(raw_application("APP-001"), _SkipsRate())
    scoring = [span for span in spans if span.agent == "risk_scoring"]
    recommendation = [span for span in spans if span.agent == "recommendation"]

    assert (
        decision.disposition,
        decision.reason_code,
        decision.reason,
        decision.scored,
        [span.error for span in scoring],
        recommendation,
    ) == (
        "refer",
        "scoring_unavailable",
        "Scoring never returned a scored case.",
        None,
        ["ScoringUnavailable"],
        [],
    )
