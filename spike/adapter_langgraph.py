"""LangGraph Adapter — thin bridge between LangGraph and the guardrail system."""

from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import MessagesState

from guardrail import Action, GuardrailGateway


class LangGraphAdapter:
    """Intercepts tool calls and routes them through the guardrail gateway."""

    def __init__(self, gateway: GuardrailGateway, agent_id: str):
        self._gateway = gateway
        self._agent_id = agent_id

    def guard_tool_calls(self, state: MessagesState) -> dict:
        """Node that checks outbound tool calls. Replaces blocked calls with denial messages."""
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", None) or []

        if not tool_calls:
            return {"messages": []}

        result_messages = []
        allowed_tool_calls = []

        for tc in tool_calls:
            action = Action(
                type="tool_call",
                tool_name=tc["name"],
                tool_args=tc["args"],
                tool_call_id=tc["id"],
            )
            verdict = self._gateway.evaluate(self._agent_id, action)

            if verdict.allowed:
                allowed_tool_calls.append(tc)
            else:
                result_messages.append(
                    ToolMessage(
                        content=f"BLOCKED: {verdict.reason}",
                        tool_call_id=tc["id"],
                    )
                )

        if result_messages:
            return {"messages": result_messages}

        return {"messages": []}
