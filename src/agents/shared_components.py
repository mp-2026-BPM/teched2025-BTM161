from langgraph_swarm import create_handoff_tool
from typing import List, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
import copy

# Data Models
@dataclass
class MenuItem:
    name: str
    price: float
    stock: int
    category: str

@dataclass
class OrderItem:
    name: str
    quantity: int
    price: float
    size: Optional[str] = None
    extras: Optional[List[str]] = field(default_factory=list)

@dataclass
class Order:
    id: str
    total: float
    status: str
    customer: str
    items: List[OrderItem] = field(default_factory=list)


class OrderInputSchema(BaseModel):
    order: Order = Field(description="The current order object")



# Coffee Shop Menu and Inventory
MENU = {
    "espresso": MenuItem("Espresso", 2.50, 20, "coffee"),
    "latte": MenuItem("Latte", 4.00, 15, "coffee"),
    "cappuccino": MenuItem("Cappuccino", 3.75, 18, "coffee"),
    "americano": MenuItem("Americano", 3.00, 22, "coffee"),
    "croissant": MenuItem("Croissant", 2.75, 8, "pastry"),
    "muffin": MenuItem("Muffin", 3.25, 12, "pastry"),
    "sandwich": MenuItem("Sandwich", 6.50, 5, "food")
}

# Global state for demonstration
class InventoryManager:
    def __init__(self):
        self.reset()

    def reset(self):
        self.inventory = copy.deepcopy(MENU)

# Create a single, shared instance of the inventory manager
inventory_manager = InventoryManager()


# Handoff Tools
transfer_to_inventory = create_handoff_tool(
    agent_name="inventory_agent",
    description="Transfer to inventory agent to check item availability."
)

transfer_to_barista = create_handoff_tool(
    agent_name="barista_agent", 
    description="Transfer to barista agent to prepare the order."
)

transfer_to_customer_service = create_handoff_tool(
    agent_name="customer_service_agent",
    description="Transfer to customer service agent for issues, complaints, or order modifications."
)

transfer_to_order_agent = create_handoff_tool(
    agent_name="order_agent",
    description="Transfer back to order agent for new or modified orders."
)
