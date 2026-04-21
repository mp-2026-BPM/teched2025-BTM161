from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import random
from pydantic import BaseModel, Field
from typing import Optional
from .shared_components import (
    MENU, Order, OrderItem,
    transfer_to_inventory, transfer_to_customer_service
)
import json
from dataclasses import asdict

class CustomerOrderItemSchema(BaseModel):
    name: str = Field(description="Name of the item")
    quantity: int = Field(default=1, description="Quantity of the item")
    size: Optional[str] = Field(default=None, description="Size of the item (e.g., small, medium, large)")
    extras: list[str] = Field(default_factory=list, description="List of extra options (e.g., soy milk, extra shot)")

class ProcessOrderInputSchema(BaseModel):
    order: list[CustomerOrderItemSchema] = Field(description="List of items in the order")
    customer: str = Field(description="Customer's name")

class CalculateTotalInputSchema(BaseModel):
    order: Order = Field(description="The current order object")
    discount_percent: int = Field(default=0, description="Discount percentage to apply")


# ORDER AGENT TOOLS
@tool(args_schema=ProcessOrderInputSchema)
def process_order(order: list[CustomerOrderItemSchema], customer) -> Order | str:
    """Process a customer order.
    Returns the created order details as JSON object."""

    
    try:
        ordered_items = []
        unknown_items = []
        total = 0.0
        
        # Parse the order text
        for item in order:
            item.name = item.name.lower().strip()
            
            if item.name in MENU:
                price = MENU[item.name].price * item.quantity
                
                # Charge $0.50 for each paid extra
                num_paid_extras = len([extra for extra in item.extras if extra.lower() not in {"hot", "cold", "iced"}])
                price += num_paid_extras * 0.50 * item.quantity

                # Charge $0.50 less for small size, $0.75 more for large
                if item.size:
                    size = item.size.lower()
                    if size == "small":
                        price -= 0.50 * item.quantity
                    elif size == "large":
                        price += 0.75 * item.quantity

                ordered_items.append(OrderItem(item.name, item.quantity, price, item.size, item.extras))
                total += price
            else:
                unknown_items.append(item.name)

        if unknown_items:
            return f"Error processing order.\nItems not on menu: {', '.join(unknown_items)}\nAvailable items: {', '.join(MENU.keys())}"
        
        order_id = f"ORD{random.randint(1000, 9999)}"
        current_order = Order(id=order_id, total=total, status="pending", customer=customer, items=ordered_items)
        
        order_summary = f"Order {order_id} created:\n"
        for item in ordered_items:
            extras_str = f" with {', '.join(item.extras)}" if item.extras else ""
            order_summary += f"- {item.quantity} in {item.size} {extras_str} x {item.name.title()} (${item.price:.2f})\n"
        order_summary += f"Total: ${total:.2f}"
        
        return json.dumps(asdict(current_order))
    except Exception as e:
        return f"Error processing order: {str(e)}. Please use specified format."


@tool(args_schema=CalculateTotalInputSchema)
def calculate_total(order: Order, discount_percent: int = 0):
    """Updates the order's total with optional discount."""
    
    original_total = order.total
    discount_amount = original_total * (discount_percent / 100)
    final_total = original_total - discount_amount
    
    order.total = final_total
    
    result = f"Order {order.id} Total: ${original_total:.2f}"
    if discount_percent > 0:
        result += f"\nDiscount ({discount_percent}%): -${discount_amount:.2f}"
        result += f"\nFinal Total: ${final_total:.2f}"
    
    # return result
    return json.dumps({
        "total": final_total,
        "discount": discount_amount,
        "order": asdict(order)
    })


def create_order_agent(chat_llm, prompt=None):
    """Create and return the order agent."""
    if not prompt:
        prompt = """You are a friendly order-taking agent at a coffee shop. 
        
        Your responsibilities:
        - Take customer orders and process them clearly
        - Calculate totals and apply any discounts
        - Transfer to inventory agent to check availability
        - Handle order modifications from customer service
        
        Be welcoming and helpful. Ask clarifying questions if orders are unclear.
        Always confirm the order details before transferring to inventory.
        """

    tools = [process_order, calculate_total, transfer_to_inventory, transfer_to_customer_service]

    llm_with_tools = chat_llm.bind_tools(tools)

    return create_react_agent(
        model=llm_with_tools,
        name="order_agent",
        tools=tools,
        prompt=prompt,
    )
