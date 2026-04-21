from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import random
import json
from pydantic import BaseModel, Field
from .shared_components import (
    transfer_to_customer_service, OrderInputSchema, Order
)
from dataclasses import asdict

class RemakeDrinkInputSchema(BaseModel):
    order: Order = Field(description="The current order object")
    item_name: str = Field(description="Name of the item to remake")

# BARISTA AGENT TOOLS
@tool(args_schema=OrderInputSchema)
def prepare_order(order: Order):
    """Simulate drink and food preparation with potential for errors.
    Returns a preparation report and order with updated status."""
    if order.status != "inventory_confirmed":
        return "Error: The inventory has not been confirmed. Cannot prepare the order."
    
    # Simulate preparation with 20% chance of error
    preparation_success = random.random() > 0.2
    
    prep_report = f"Preparing Order {order.id}...\n"
    
    for item in order.items:
        prep_report += f"- Making {item.quantity}x {item.name.title()}\n"
    
    if preparation_success:
        order.status = "completed"
        prep_report += "\nAll items prepared successfully"
    else:
        order.status = "preparation_error"
        failed_item = random.choice(order.items)
        prep_report += f"\nError preparing {failed_item.name.title()}"
    
    return json.dumps({
        "preparation_report": prep_report,
        "order": asdict(order)
    })

@tool
def remake_order_item(order: Order, item_name: str) -> bool:
    """Remake a specific drink or food item."""
        
    # Find the item in the order
    for item in order.items:
        if item.name == item_name.lower():
            # Simulate remake with 90% success rate
            remake_success = random.random() > 0.1
            
            if remake_success:
                order.status = "completed"
                return True
                
    return False


@tool(args_schema=OrderInputSchema)
def estimate_prep_time(order: Order) -> str:
    """Estimate preparation time for current order."""
    
    total_items = sum(item.quantity for item in order.items)
    base_time = 2  # 2 minutes base time
    time_per_item = 1.5  # 1.5 minutes per additional item
    
    estimated_time = base_time + (total_items - 1) * time_per_item
    
    return f"Estimated preparation time for Order {order.id}: {estimated_time:.1f} minutes"


def create_barista_agent(chat_llm, prompt=None):
    """Create and return the barista agent."""

    if not prompt:
        prompt = """You are a skilled barista agent responsible for drink preparation.
        
        Your responsibilities:
        - Prepare drinks and food items for orders
        - Handle preparation errors and remakes
        - Provide time estimates for orders
        - Transfer to customer service when issues arise
        
        Take pride in your craft and maintain quality standards. If something goes wrong, be honest about it."""

    tools = [prepare_order, remake_order_item, estimate_prep_time, transfer_to_customer_service]

    llm_with_tools = chat_llm.bind_tools(tools)

    return create_react_agent(
        model=llm_with_tools,
        name="barista_agent",
        tools=tools,
        prompt=prompt,
    )
