"""
Guardrail Architecture Spike
=============================
Demonstrates the decoupled guardrail system:
- Framework-agnostic guardrail (gateway, pipeline, registry, rules)
- LangGraph adapter (thin bridge)
- A fake agent that attempts two actions: one allowed, one denied

Run: .venv/bin/python spike/guardrail_demo.py
"""

from __future__ import annotations

import json
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph, MessagesState

from guardrail import (
    GuardrailRegistry,
    GuardrailPipeline,
    GuardrailGateway,
    MaxDiscountRule,
    AllowProcessOrderRule,
)
from adapter_langgraph import LangGraphAdapter


# ═══════════════════════════════════════════════════════════════════════════════
# FAKE TOOLS (no real DB, deterministic)
# ═══════════════════════════════════════════════════════════════════════════════


def fake_process_order(order: list, customer: str) -> str:
    order_id = f"ORD-{uuid.uuid4().hex[:6]}"
    return json.dumps({"order_id": order_id, "status": "created", "customer": customer})


def fake_calculate_total(order_id: str, discount_percent: int = 0) -> str:
    total = 12.50
    final = total * (1 - discount_percent / 100)
    return json.dumps({"order_id": order_id, "total": final})


TOOL_DISPATCH = {
    "process_order": fake_process_order,
    "calculate_total": fake_calculate_total,
}


# ═══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH DEMO
# ═══════════════════════════════════════════════════════════════════════════════


def build_demo_graph(adapter: LangGraphAdapter):
    """Builds a minimal LangGraph: agent → guardrail → tool execution."""

    actions = [
        AIMessage(
            content="Processing order...",
            tool_calls=[{
                "id": "call_1",
                "name": "process_order",
                "args": {"order": [{"name": "steak", "quantity": 1}], "customer": "Alice"},
            }],
        ),
        AIMessage(
            content="Applying discount...",
            tool_calls=[{
                "id": "call_2",
                "name": "calculate_total",
                "args": {"order_id": "ORD-abc123", "discount_percent": 50},
            }],
        ),
    ]
    action_iter = iter(actions)

    def agent_node(state: MessagesState) -> dict:
        msg = next(action_iter, None)
        if msg is None:
            return {"messages": [AIMessage(content="Done.")]}
        return {"messages": [msg]}

    def guardrail_node(state: MessagesState) -> dict:
        return adapter.guard_tool_calls(state)

    def tool_node(state: MessagesState) -> dict:
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", None) or []

        results = []
        for tc in tool_calls:
            fn = TOOL_DISPATCH.get(tc["name"])
            if fn:
                result = fn(**tc["args"])
                print(f"[RESULT] {tc['name']} executed successfully")
                results.append(ToolMessage(content=result, tool_call_id=tc["id"]))
        return {"messages": results}

    def route_after_guardrail(state: MessagesState) -> str:
        messages = state["messages"]
        last_ai = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai = msg
                break
        if last_ai and last_ai.tool_calls:
            return "tools"
        return "agent"

    def route_after_agent(state: MessagesState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "guardrail"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"guardrail": "guardrail", END: END})
    graph.add_conditional_edges("guardrail", route_after_guardrail, {"tools": "tools", "agent": "agent"})
    graph.add_edge("tools", "agent")

    return graph.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 60)
    print("GUARDRAIL ARCHITECTURE SPIKE")
    print("=" * 60)

    # 1. Set up guardrail system (framework-agnostic)
    registry = GuardrailRegistry()
    registry.register(MaxDiscountRule())
    registry.register(AllowProcessOrderRule())

    pipeline = GuardrailPipeline(registry)
    gateway = GuardrailGateway(pipeline)

    # 2. Create LangGraph adapter (thin bridge)
    adapter = LangGraphAdapter(gateway, agent_id="server_agent")

    # 3. Build and run the graph
    app = build_demo_graph(adapter)
    result = app.invoke({"messages": [HumanMessage(content="Start")]})

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    for msg in result["messages"]:
        role = type(msg).__name__
        content = msg.content[:80] if msg.content else ""
        blocked = " ⛔" if content.startswith("BLOCKED") else ""
        print(f"  {role}: {content}{blocked}")


if __name__ == "__main__":
    main()
