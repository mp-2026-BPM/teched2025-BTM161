"""Core data types for the guardrail system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Action:
    type: str  # "tool_call"
    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str


@dataclass
class Verdict:
    allowed: bool
    reason: str = ""


class GuardrailRule(Protocol):
    """A single rule. Returns a Verdict if applicable, None if not."""

    name: str

    def evaluate(self, agent_id: str, action: Action) -> Verdict | None: ...
