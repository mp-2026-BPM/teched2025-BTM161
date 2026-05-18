"""Guardrail Gateway — single entry point for the guardrail system."""

from __future__ import annotations

from .types import Action, Verdict
from .pipeline import GuardrailPipeline


class GuardrailGateway:
    def __init__(self, pipeline: GuardrailPipeline):
        self._pipeline = pipeline

    def evaluate(self, agent_id: str, action: Action) -> Verdict:
        return self._pipeline.evaluate(agent_id, action)
