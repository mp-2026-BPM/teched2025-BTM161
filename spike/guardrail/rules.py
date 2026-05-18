"""Concrete guardrail rules."""

from __future__ import annotations

from dataclasses import dataclass

from .types import Action, Verdict


@dataclass
class MaxDiscountRule:
    """Rejects calculate_total calls with discount exceeding the cap."""

    name: str = "max_discount_15pct"
    max_percent: int = 15

    def evaluate(self, agent_id: str, action: Action) -> Verdict | None:
        if action.tool_name != "calculate_total":
            return None
        discount = action.tool_args.get("discount_percent", 0)
        if discount > self.max_percent:
            return Verdict(
                allowed=False,
                reason=f"discount {discount}% exceeds maximum {self.max_percent}%",
            )
        return Verdict(allowed=True, reason="discount within limit")


@dataclass
class AllowProcessOrderRule:
    """Explicitly allows process_order calls."""

    name: str = "allow_process_order"

    def evaluate(self, agent_id: str, action: Action) -> Verdict | None:
        if action.tool_name != "process_order":
            return None
        return Verdict(allowed=True, reason="process_order permitted")
