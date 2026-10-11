"""Model protocol, Ollama client, and the shared completion helpers.

Tests use ScriptedModel. Live runs use Ollama (Qwen).
Model calls retry TimeoutError inside complete_turn.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol, TypeVar, cast

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
_RETRY_ATTEMPTS = 3

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ToolCall:
    """One function the model asked the host to run."""

    name: str
    arguments: dict[str, Any]
    id: str = ""


@dataclass(frozen=True)
class Completion:
    """One model turn. `text` is empty when the turn is only tool calls."""

    text: str
    input_tokens: int
    output_tokens: int
    tool_calls: tuple[ToolCall, ...] = ()


class Model(Protocol):
    """Anything that can complete one turn. Tools are optional."""

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0,
        messages: list[dict[str, Any]] | None = None,
    ) -> Completion:
        """Return assistant text, token counts, and any tool calls."""


def _backoff(retry_state: RetryCallState) -> float:
    """Wait base, then base times 2, capped at 4 seconds. Zero when the env base is 0."""
    base = float(os.environ.get("UNDERWRITING_RETRY_BASE_SECONDS", "0.5"))
    if base == 0:
        return 0.0
    return float(wait_exponential(multiplier=base, min=base, max=4)(retry_state))


class ScriptedModel:
    """Returns a known string. Token counts are len(text) // 4. Cost of these runs is $0."""

    def __init__(self, response: str) -> None:
        """Store the text complete() will return."""
        self.response = response

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0,
        messages: list[dict[str, Any]] | None = None,
    ) -> Completion:
        """Return the stored text and ignore schema, tools, and temperature."""
        del schema, tools, temperature
        prompt = system + user if messages is None else json.dumps(messages)
        return Completion(
            text=self.response,
            input_tokens=len(prompt) // 4,
            output_tokens=len(self.response) // 4,
        )


class OllamaModel:
    """Live model. Talks to local Ollama through the OpenAI client."""

    def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0,
        messages: list[dict[str, Any]] | None = None,
    ) -> Completion:
        """Send one chat completion and return its text, tokens, and tool calls."""
        return chat_completion(
            system=system,
            user=user,
            schema=schema,
            tools=tools,
            temperature=temperature,
            messages=messages,
        )


@lru_cache
def get_llm_client() -> OpenAI:
    """Client for Ollama's OpenAI-compatible endpoint. Ollama does not check the API key."""
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return OpenAI(base_url=base_url, api_key="ollama")


def default_model() -> str:
    """Return the Ollama model name, defaulting to qwen3:8b."""
    return os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)


def _parse_tool_calls(message: Any) -> tuple[ToolCall, ...]:
    """Read OpenAI-style tool calls off a chat message."""
    calls: list[ToolCall] = []
    for call in message.tool_calls or []:
        raw = call.function.arguments or "{}"
        arguments = json.loads(raw) if isinstance(raw, str) else raw
        calls.append(ToolCall(name=call.function.name, arguments=arguments, id=call.id or ""))
    return tuple(calls)


def chat_completion(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0,
    schema: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> Completion:
    """Run one chat completion against local Ollama."""
    kwargs: dict[str, Any] = {}
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": schema},
        }
    if tools is not None:
        kwargs["tools"] = tools
    payload = messages
    if payload is None:
        payload = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    client = get_llm_client()
    response = client.chat.completions.create(
        model=model or default_model(),
        messages=cast(list[ChatCompletionMessageParam], payload),
        temperature=temperature,
        **kwargs,
    )
    message = response.choices[0].message
    usage = response.usage
    return Completion(
        text=message.content or "",
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        tool_calls=_parse_tool_calls(message),
    )


def complete_turn(
    model: Model,
    system: str,
    user: str,
    *,
    schema: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0,
    messages: list[dict[str, Any]] | None = None,
) -> Completion:
    """Call the model. TimeoutError is retried. Any other error propagates."""
    completion: Completion | None = None
    for attempt in Retrying(
        stop=stop_after_attempt(_RETRY_ATTEMPTS),
        wait=_backoff,
        retry=retry_if_exception_type(TimeoutError),
        reraise=True,
    ):
        with attempt:
            completion = model.complete(
                system,
                user,
                schema=schema,
                tools=tools,
                temperature=temperature,
                messages=messages,
            )
    if completion is None:
        raise RuntimeError("model call did not run")
    return completion


def complete_as(
    model: Model,
    system: str,
    user: str,
    result_type: type[T],
    *,
    temperature: float = 0,
) -> tuple[T, int, int]:
    """Send the model's schema, then validate the reply into that model.

    TimeoutError is retried. A reply that fails validation is not.
    """
    completion = complete_turn(
        model,
        system,
        user,
        schema=result_type.model_json_schema(),
        temperature=temperature,
    )
    parsed = result_type.model_validate_json(completion.text)
    return parsed, completion.input_tokens, completion.output_tokens
