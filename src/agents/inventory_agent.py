from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import json
from dataclasses import asdict

from .shared_components import (
    inventory_manager, MENU, Order, OrderInputSchema,
    transfer_to_barista, transfer_to_customer_service
)
from ..llm import bind_tools_sequential


# INVENTORY AGENT TOOLS
@tool(args_schema=OrderInputSchema)
def check_inventory(order: Order):
    """Check if all items in current order are available and return a structured JSON-like report."""
    items_report = []
    all_available = True
    unavailable_items = []

    for order_item in order.items:
        menu_item = inventory_manager.inventory.get(order_item.name)
        if menu_item is None:
            return "Error: Item '{order_item.name}' not found in inventory."
        else:
            available_qty = menu_item.stock
            if available_qty >= order_item.quantity:
                status = "available"
            elif available_qty > 0:
                status = "partial"
            else:
                status = "out_of_stock"

        items_report.append({
            "name": order_item.name,
            "requested_quantity": order_item.quantity,
            "available_quantity": available_qty,
            "status": status
        })

        if status != "available":
            unavailable_items.append(order_item.name)
            all_available = False

    order.status = "inventory_confirmed" if all_available else "inventory_issues"

    report = {
        "order_id": order.id,
        "all_available": all_available,
        "details": items_report,
        "unavailable_items": unavailable_items
    }

    return json.dumps({
        "report": report,
        "order": asdict(order)
    })


@tool(args_schema=OrderInputSchema)
def update_stock(order: Order):
    """Update inventory after order confirmation and return a technical JSON-like report."""

    if order.status != "inventory_confirmed":
        return "Error: Cannot update stock - order not confirmed or no active order."

    items_report = []

    for order_item in order.items:
        inv_item = inventory_manager.inventory.get(order_item.name)
        if inv_item is None:
            raise KeyError(f"Item '{order_item.name}' not found in inventory.")

        stock_before = inv_item.stock
        inventory_manager.inventory[order_item.name].stock -= order_item.quantity

        items_report.append({
            "name": order_item.name,
            "quantity_removed": order_item.quantity,
            "previous_stock": stock_before,
            "new_stock": stock_before - order_item.quantity
        })

    return json.dumps({
        "report": {
            "order_id": order.id,
            "status": "success",
            "total_items_updated": len(items_report),
            "items": items_report,
            "note": "Order ready for barista preparation."
        },
        "order": asdict(order)
    })


@tool
def get_alternatives(item_name: str):
    """Get alternative items for out-of-stock products."""
    if item_name not in MENU:
        return f"Error: Item '{item_name}' not found in menu."

    original_item = MENU[item_name]
    alternatives = []

    for name, item in inventory_manager.inventory.items():
        if (name != item_name and
            item.category == original_item.category and
                item.stock > 0):
            alternatives.append(
                f"{name.title()} (${item.price:.2f}) - {item.stock} available")

    return json.dumps({
        "alternatives": alternatives,
        "original_item": original_item.name,
        "category": original_item.category
    })


def create_inventory_agent(chat_llm, prompt=None):
    """Create and return the inventory agent."""
    if not prompt:
        prompt = """You are the inventory management agent for a coffee shop.
        
        Your responsibilities:
        - Check item availability for orders
        - Update stock levels after confirmation
        - Find alternatives for out-of-stock items
        - Transfer to barista when items are available
        - Transfer to customer service when items are unavailable
        
        Be thorough in your inventory checks and proactive about suggesting alternatives."""

    tools = [check_inventory, update_stock, get_alternatives,
             transfer_to_barista, transfer_to_customer_service]

    llm_with_tools = bind_tools_sequential(chat_llm, tools)

    return create_react_agent(
        model=llm_with_tools,
        name="inventory_agent",
        tools=tools,
        prompt=prompt,
    )
