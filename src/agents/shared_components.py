from enum import Enum
from typing import List, Optional
from datetime import datetime, timezone

from langgraph_swarm import create_handoff_tool
from pydantic import BaseModel, Field
from sqlalchemy import Enum as SAEnum
from sqlmodel import SQLModel, Field as SQLField, Relationship, Column, JSON


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    PENDING = "pending"
    INVENTORY_CONFIRMED = "inventory_confirmed"
    INVENTORY_ISSUES = "inventory_issues"
    IN_PREPARATION = "in_preparation"
    COMPLETED = "completed"
    PREPARATION_ERROR = "preparation_error"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class Size(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# ---------------------------------------------------------------------------
# Global allowed extras
# ---------------------------------------------------------------------------

ALLOWED_EXTRAS: set[str] = {
    "soy milk", "oat milk", "almond milk",
    "extra shot", "decaf",
    "whipped cream", "vanilla syrup", "caramel syrup",
    "hot", "cold", "iced",
}


# ---------------------------------------------------------------------------
# SQLModel table classes
# ---------------------------------------------------------------------------

class MenuItem(SQLModel, table=True):
    __tablename__ = "inventory"

    name: str = SQLField(primary_key=True)
    price: float
    stock: int
    category: str


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: int | None = SQLField(default=None, primary_key=True)
    order_id: int = SQLField(foreign_key="orders.id")
    name: str = SQLField(foreign_key="inventory.name")
    quantity: int
    price: float
    size: Size | None = SQLField(
        default=None,
        sa_column=Column(SAEnum(Size, values_callable=lambda e: [m.value for m in e]),
                         nullable=True),
    )
    extras: list[str] = SQLField(default_factory=list, sa_column=Column(JSON))

    order: Optional["Order"] = Relationship(back_populates="items")


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: int | None = SQLField(default=None, primary_key=True)
    customer: str
    status: OrderStatus = SQLField(
        default=OrderStatus.PENDING,
        sa_column=Column(SAEnum(OrderStatus, values_callable=lambda e: [m.value for m in e]),
                         nullable=False),
    )
    total: float = 0.0
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(timezone.utc))

    items: List[OrderItem] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )

    @property
    def order_id_str(self) -> str:
        return f"ORD{self.id:04d}" if self.id else "ORD????"


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

MENU = {
    "espresso": MenuItem(name="espresso", price=2.50, stock=20, category="coffee"),
    "latte": MenuItem(name="latte", price=4.00, stock=15, category="coffee"),
    "cappuccino": MenuItem(name="cappuccino", price=3.75, stock=18, category="coffee"),
    "americano": MenuItem(name="americano", price=3.00, stock=22, category="coffee"),
    "croissant": MenuItem(name="croissant", price=2.75, stock=8, category="pastry"),
    "muffin": MenuItem(name="muffin", price=3.25, stock=12, category="pastry"),
    "sandwich": MenuItem(name="sandwich", price=6.50, stock=5, category="food"),
}


# ---------------------------------------------------------------------------
# Pydantic schema for tools that operate on an existing order by ID
# ---------------------------------------------------------------------------

class OrderIdSchema(BaseModel):
    order_id: str = Field(description="The order ID (e.g. 'ORD0001')")


# ---------------------------------------------------------------------------
# Handoff Tools
# ---------------------------------------------------------------------------

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
