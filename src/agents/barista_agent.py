from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import logging
import random
import json
from pydantic import BaseModel, Field

logger = logging.getLogger("coffee_shop.barista_agent")

from src.llm import bind_tools_sequential

from .shared_components import (
    OrderIdSchema, OrderStatus,
    transfer_to_customer_service,
)
from .order_store import load_order, get_order
from .order_state_machine import state_machine, InvalidTransitionError


class RemakeItemSchema(BaseModel):
    order_id: str = Field(description="The order ID string")
    item_name: str = Field(description="Name of the item to remake")


# BARISTA AGENT TOOLS
@tool(args_schema=OrderIdSchema)
def prepare_order(order_id: str) -> str:
    """Simulate drink and food preparation with potential for errors.
    Returns a preparation report."""
    order = load_order(order_id)
    if order is None:
        return f"Error: Order '{order_id}' not found."
    if order.status != OrderStatus.INVENTORY_CONFIRMED:
        return f"Error: Inventory not confirmed for order {order_id}. Cannot prepare."

    try:
        order = state_machine.transition(order, OrderStatus.IN_PREPARATION, context="prepare_order: starting")
    except InvalidTransitionError as e:
        return json.dumps({"order_id": order_id, "error": f"Cannot start preparation: {e}"})

    # Simulate preparation with 20% chance of error
    preparation_success = random.random() > 0.2

    prep_report = f"Preparing Order {order_id}...\n"
    for item in order.items:
        prep_report += f"- Making {item.quantity}x {item.name.title()}\n"

    if preparation_success:
        try:
            order = state_machine.transition(order, OrderStatus.COMPLETED, context="prepare_order: success")
        except InvalidTransitionError as e:
            return json.dumps({"order_id": order_id, "error": f"Cannot mark order as completed after preparation: {e}"})
        prep_report += "\nAll items prepared successfully!"
    else:
        failed_item = random.choice(order.items)
        prep_report += f"\nError preparing {failed_item.name.title()}"
        try:
            order = state_machine.transition(order, OrderStatus.PREPARATION_ERROR,
                                             context=f"prepare_order: failed on {failed_item.name}")
        except InvalidTransitionError as e:
            return json.dumps({"order_id": order_id, "error": f"Cannot record preparation error: {e}"})
    return json.dumps({"order_id": order_id, "status": order.status.value, "summary": prep_report})


@tool(args_schema=RemakeItemSchema)
def remake_order_item(order_id: str, item_name: str) -> str:
    """Remake a specific drink or food item."""
    order = load_order(order_id)
    if order is None:
        return f"Error: Order '{order_id}' not found."

    for item in order.items:
        if item.name == item_name.lower():
            # Simulate remake with 90% success rate
            remake_success = random.random() > 0.1

            if remake_success:
                try:
                    order = state_machine.transition(order, OrderStatus.COMPLETED,
                                                     context=f"remake_order_item: {item_name}")
                except InvalidTransitionError as e:
                    return json.dumps({
                        "order_id": order_id,
                        "error": f"Cannot mark order as completed after remake: {e}",
                    })
                return json.dumps({
                    "order_id": order_id,
                    "status": OrderStatus.COMPLETED.value,
                    "summary": f"Successfully remade {item_name.title()} for order {order_id}.",
                })
            else:
                logger.debug(f"Remake of {item_name} for order {order_id} failed")
                return json.dumps({
                    "order_id": order_id,
                    "status": order.status.value,
                    "summary": f"Failed to remake {item_name.title()}. Please try again.",
                })

    return f"Error: Item '{item_name}' not found in order {order_id}."


@tool(args_schema=OrderIdSchema)
def estimate_prep_time(order_id: str) -> str:
    """Estimate preparation time for an order."""
    order = load_order(order_id)
    if order is None:
        return f"Error: Order '{order_id}' not found."

    total_items = sum(item.quantity for item in order.items)
    base_time = 2  # 2 minutes base time
    time_per_item = 1.5  # 1.5 minutes per additional item
    estimated_time = base_time + (total_items - 1) * time_per_item

    return f"Estimated preparation time for Order {order_id}: {estimated_time:.1f} minutes ({total_items} item(s))"


def create_barista_agent(chat_llm, prompt=None):
    """Create and return the barista agent."""
    if not prompt:
        prompt = """You are a skilled barista agent responsible for drink and food preparation.

        Your job:
        - Prepare the order using prepare_order.
        - If preparation succeeds: inform the customer their order is ready. Your job is done.
        - If preparation fails: attempt a remake with remake_order_item. If that also fails, transfer to customer service.

        You can transfer to:
        - Customer service agent: when preparation fails and cannot be resolved by remaking

        Take pride in your craft. If something goes wrong, be honest about it.
        """

    tools = [prepare_order, remake_order_item, estimate_prep_time, get_order, transfer_to_customer_service]

    llm_with_tools = bind_tools_sequential(chat_llm, tools)

    return create_react_agent(
        model=llm_with_tools,
        name="barista_agent",
        tools=tools,
        prompt=prompt,
    )
