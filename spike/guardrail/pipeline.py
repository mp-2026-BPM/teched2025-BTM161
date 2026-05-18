"""Guardrail Pipeline — evaluates actions against all registered rules."""

from __future__ import annotations

from .types import Action, Verdict
from .registry import GuardrailRegistry


class GuardrailPipeline:
    """Runs an action through all rules. Short-circuits on first denial."""

    def __init__(self, registry: GuardrailRegistry):
        self._registry = registry

    def evaluate(self, agent_id: str, action: Action) -> Verdict:
        print(f"\n[GUARDRAIL] Evaluating: {agent_id} → {action.tool_name}")
        for rule in self._registry.rules:
            verdict = rule.evaluate(agent_id, action)
            if verdict is None:
                print(f"[GUARDRAIL] Rule '{rule.name}': SKIP (not applicable)")
                continue
            if not verdict.allowed:
                print(f"[GUARDRAIL] Rule '{rule.name}': DENY — {verdict.reason}")
                return verdict
            print(f"[GUARDRAIL] Rule '{rule.name}': ALLOW")
        return Verdict(allowed=True, reason="no rule denied")
