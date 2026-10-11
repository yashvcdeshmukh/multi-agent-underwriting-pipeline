"""Only coordinator. Fixed order: intake, enrichment, scoring, recommendation.

Every model call retries TimeoutError three times. If it still times out, return
a referral that names that step and do not call the later agents. If scoring
never returns a scored case, refer with scoring_unavailable and no scored case.
"""

from __future__ import annotations

import json

from underwriting.agents.enrichment import enrichment_agent
from underwriting.agents.intake import intake_agent
from underwriting.agents.recommendation import recommendation_agent
from underwriting.agents.scoring import ScoringUnavailable, risk_scoring_agent
from underwriting.domain.models import AgentName, Decision, ReasonCode, ScoredCase
from underwriting.fixtures.applications import raw_application
from underwriting.llm import Model, OllamaModel
from underwriting.tracing import Span, append_span

_NOT_PRICED_REASON = "Scoring never returned a scored case."
_TIMEOUTS: dict[AgentName, tuple[ReasonCode, str]] = {
    "intake": ("intake_unavailable", "Intake timed out after retries."),
    "enrichment": ("enrichment_unavailable", "Enrichment timed out after retries."),
    "risk_scoring": ("scoring_unavailable", "Scoring timed out after retries."),
    "recommendation": (
        "recommendation_unavailable",
        "Recommendation timed out after retries.",
    ),
}


def case_id_from_application(raw: str) -> str:
    """Return the application id from the first 'Application ID:' line."""
    prefix = "Application ID:"
    for line in raw.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise ValueError("application id is missing")


def _refer(
    case_id: str,
    reason_code: ReasonCode,
    reason: str,
    scored: ScoredCase | None = None,
) -> Decision:
    """Return a referral. Later agents are not called."""
    return Decision(
        case_id=case_id,
        scored=scored,
        disposition="refer",
        reason_code=reason_code,
        reason=reason,
    )


def _timeout_decision(
    case_id: str,
    agent: AgentName,
    scored: ScoredCase | None = None,
) -> Decision:
    """Return the referral for a model call that timed out after retries."""
    reason_code, reason = _TIMEOUTS[agent]
    return _refer(case_id, reason_code, reason, scored)


def underwrite(raw: str, model: Model) -> tuple[Decision, list[Span]]:
    """Run the four agents in order and return the decision plus the spans."""
    spans: list[Span] = []
    case_id = case_id_from_application(raw)
    try:
        intake = append_span(
            spans,
            case_id=case_id,
            agent="intake",
            received=raw,
            call=lambda: intake_agent(raw, model),
        )
    except TimeoutError:
        return _timeout_decision(case_id, "intake"), spans
    try:
        enriched = append_span(
            spans,
            case_id=case_id,
            agent="enrichment",
            received=intake,
            call=lambda: enrichment_agent(intake, model),
        )
    except TimeoutError:
        return _timeout_decision(case_id, "enrichment"), spans
    try:
        scored = append_span(
            spans,
            case_id=case_id,
            agent="risk_scoring",
            received=enriched,
            call=lambda: risk_scoring_agent(enriched, model),
        )
    except TimeoutError:
        return _timeout_decision(case_id, "risk_scoring"), spans
    except ScoringUnavailable:
        return _refer(case_id, "scoring_unavailable", _NOT_PRICED_REASON), spans
    try:
        decision = append_span(
            spans,
            case_id=case_id,
            agent="recommendation",
            received=scored,
            call=lambda: recommendation_agent(scored, model),
        )
    except TimeoutError:
        return _timeout_decision(case_id, "recommendation", scored), spans
    return decision, spans


def main() -> None:
    """Underwrite APP-001, APP-002, and APP-003 with local Ollama and print each decision."""
    model = OllamaModel()
    for case_id in ("APP-001", "APP-002", "APP-003"):
        decision, spans = underwrite(raw_application(case_id), model)
        print(
            json.dumps(
                {
                    "case_id": case_id,
                    "disposition": decision.disposition,
                    "reason_code": decision.reason_code,
                    "guideline_id": decision.guideline_id,
                    "spans": [span.model_dump(mode="json") for span in spans],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
