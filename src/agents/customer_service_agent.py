from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from .shared_components import (
    transfer_to_order_agent, transfer_to_barista, transfer_to_inventory, OrderInputSchema, Order
)
from pydantic import BaseModel, Field
from dataclasses import asdict
import json

class OfferPartialRefundInputSchema(BaseModel):
    order: Order = Field(description="The current order object")
    refund_percent: int = Field(default=50, description="Discount percentage to apply")


# CUSTOMER SERVICE AGENT TOOLS
@tool(args_schema=OrderInputSchema)
def offer_refund(order: Order):
    """Process a refund for the current order."""
    refund_amount = order.total
    order.status = "refunded"
    
    return json.dumps({
        "refund_amount": refund_amount,
        "original_total": order.total,
        "new_total": 0.0,
        "order": asdict(order)
    })


@tool(args_schema=OfferPartialRefundInputSchema)
def offer_partial_refund(order: Order, refund_percent: int):
    """Process a partial refund for the current order."""

    original_total = order.total
    discount_amount = original_total * (refund_percent / 100)
    final_total = original_total - discount_amount
    
    order.total = final_total
    
    return json.dumps({
        "refund_amount": discount_amount,
        "original_total": original_total,
        "new_total": final_total,
        "order": asdict(order)
    })


def create_customer_service_agent(chat_llm, prompt=None):
    """Create and return the customer service agent."""
    if not prompt:
        prompt = """You are a customer service agent focused on customer satisfaction.
        
        Your responsibilities:
        - Handle customer complaints with empathy
        - Offer (partial) refunds, compensation, or discounts for the next order when appropriate
        - You can check with the inventory agent for alternatives if items are unavailable
        - Transfer back to appropriate agents for resolution
        
        Always prioritize customer satisfaction and be generous with compensation when needed."""

    tools = [offer_refund, offer_partial_refund, transfer_to_order_agent, transfer_to_barista, transfer_to_inventory]

    llm_with_tools = chat_llm.bind_tools(tools, parallel_tool_calls=False)

    return create_react_agent(
        model=llm_with_tools,
        name="customer_service_agent",
        tools=tools,
        prompt=prompt,
    )
