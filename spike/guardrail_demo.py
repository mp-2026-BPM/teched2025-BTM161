"""
Guardrail Architecture Spike (LLM-driven)
==========================================
Demonstrates the decoupled guardrail system with a real LLM agent:
- Framework-agnostic guardrail (gateway, pipeline, registry, rules)
- LangGraph adapter (thin bridge)
- An LLM agent that is prompted to trigger both an allowed and a denied action

Run: cd spike && ../.venv/bin/python guardrail_demo.py
"""

from __future__ import annotations

import json
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph, MessagesState
from pydantic import BaseModel, Field

from llm import _create_chat_llm, bind_tools_sequential
from guardrail import (
    GuardrailRegistry,
    GuardrailPipeline,
    GuardrailGateway,
    MaxDiscountRule,
    AllowProcessOrderRule,
)
from adapter_langgraph import LangGraphAdapter


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS (simple stubs — no real DB)
# ═══════════════════════════════════════════════════════════════════════════════


class ProcessOrderInput(BaseModel):
    item: str = Field(description="Name of the menu item")
    quantity: int = Field(default=1, description="Quantity")
    customer: str = Field(description="Customer name")


class CalculateTotalInput(BaseModel):
    order_id: str = Field(description="The order ID")
    discount_percent: int = Field(default=0, description="Discount percentage to apply")


@tool(args_schema=ProcessOrderInput)
def process_order(item: str, quantity: int, customer: str) -> str:
    """Process a customer order. Creates the order and returns an order ID."""
    order_id = f"ORD-{uuid.uuid4().hex[:6]}"
    total = quantity * 12.50
    return json.dumps({
        "order_id": order_id,
        "item": item,
        "quantity": quantity,
        "customer": customer,
        "total": total,
        "status": "created",
    })


@tool(args_schema=CalculateTotalInput)
def calculate_total(order_id: str, discount_percent: int = 0) -> str:
    """Recalculate order total with an optional discount percentage."""
    base_total = 12.50
    final = base_total * (1 - discount_percent / 100)
    return json.dumps({"order_id": order_id, "total": final, "discount_applied": discount_percent})


TOOLS = [process_order, calculate_total]

SYSTEM_PROMPT = """You are a server agent at a restaurant. You have two tasks to complete IN ORDER:

1. FIRST: Process an order for customer "Alice" who wants 1 steak. Use the process_order tool.
2. SECOND: After the order is processed, apply a 50% discount using calculate_total
   (use the order_id from step 1, set discount_percent=50).

Complete both tasks. Do not ask for confirmation — just execute them one at a time."""


# ═══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH: Manual agent loop with guardrail interception
# ═══════════════════════════════════════════════════════════════════════════════


def build_guarded_agent(adapter: LangGraphAdapter):
    """Builds a LangGraph with: LLM call → guardrail check → tool execution loop."""

    llm = _create_chat_llm()
    llm_with_tools = bind_tools_sequential(llm, TOOLS)

    def llm_node(state: MessagesState) -> dict:
        """Call the LLM once — produces either a text response or tool calls."""
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def guardrail_node(state: MessagesState) -> dict:
        return adapter.guard_tool_calls(state)

    def tool_node(state: MessagesState) -> dict:
        """Execute allowed tool calls."""
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", None) or []

        results = []
        for tc in tool_calls:
            tool_fn = next((t for t in TOOLS if t.name == tc["name"]), None)
            if tool_fn:
                result = tool_fn.invoke(tc["args"])
                print(f"[RESULT] {tc['name']} executed successfully")
                results.append(ToolMessage(content=result, tool_call_id=tc["id"]))
        return {"messages": results}

    def route_after_llm(state: MessagesState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "guardrail"
        return END

    def route_after_guardrail(state: MessagesState) -> str:
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    return "tools"
                break
        return "llm"

    graph = StateGraph(MessagesState)
    graph.add_node("llm", llm_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", route_after_llm, {"guardrail": "guardrail", END: END})
    graph.add_conditional_edges("guardrail", route_after_guardrail, {"tools": "tools", "llm": "llm"})
    graph.add_edge("tools", "llm")

    return graph.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════


def _content_str(content) -> str:
    """Normalize content to string (handles Anthropic list-of-blocks format)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    return str(content)


def main():
    print("=" * 60)
    print("GUARDRAIL ARCHITECTURE SPIKE (LLM-driven)")
    print("=" * 60)

    # 1. Set up guardrail system (framework-agnostic)
    registry = GuardrailRegistry()
    registry.register(MaxDiscountRule())
    registry.register(AllowProcessOrderRule())

    pipeline = GuardrailPipeline(registry)
    gateway = GuardrailGateway(pipeline)

    # 2. Create LangGraph adapter (thin bridge)
    adapter = LangGraphAdapter(gateway, agent_id="server_agent")

    # 3. Build and run the guarded agent
    app = build_guarded_agent(adapter)
    result = app.invoke({"messages": [HumanMessage(content="Start taking the order.")]})

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    for msg in result["messages"]:
        role = type(msg).__name__
        content = _content_str(msg.content)[:100]
        blocked = " ⛔" if content.startswith("BLOCKED") else ""
        print(f"  {role}: {content}{blocked}")


if __name__ == "__main__":
    main()
