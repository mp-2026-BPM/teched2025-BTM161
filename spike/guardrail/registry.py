"""Guardrail Registry — holds all registered rules."""

from __future__ import annotations

from .types import GuardrailRule


class GuardrailRegistry:
    def __init__(self):
        self._rules: list[GuardrailRule] = []

    def register(self, rule: GuardrailRule):
        self._rules.append(rule)

    @property
    def rules(self) -> list[GuardrailRule]:
        return self._rules
