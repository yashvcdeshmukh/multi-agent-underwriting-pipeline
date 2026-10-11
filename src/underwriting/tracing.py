"""One span per agent call. The pipeline prints these as JSON."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from underwriting.domain.models import AgentName


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    agent: AgentName
    received: Any
    produced: Any
    duration_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float = 0
    error: str | None = None


def _payload(value: Any) -> Any:
    """Dump a Pydantic model to JSON-ready data. Leave other values as they are."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def append_span(
    spans: list[Span],
    *,
    case_id: str,
    agent: AgentName,
    received: Any,
    call: Callable[[], tuple[Any, int, int]],
) -> Any:
    """Run `call`, append a span, and re-raise.

    `call` returns (produced, input_tokens, output_tokens). Local Ollama runs
    record cost_usd as 0. A rate card is applied later in the write-up.
    """
    started = time.perf_counter()
    try:
        produced, input_tokens, output_tokens = call()
    except Exception as exc:
        spans.append(
            Span(
                case_id=case_id,
                agent=agent,
                received=_payload(received),
                produced=None,
                duration_ms=(time.perf_counter() - started) * 1000,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0,
                error=type(exc).__name__,
            )
        )
        raise
    spans.append(
        Span(
            case_id=case_id,
            agent=agent,
            received=_payload(received),
            produced=_payload(produced),
            duration_ms=(time.perf_counter() - started) * 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0,
            error=None,
        )
    )
    return produced
