from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List
from enum import Enum


class OrderStatusSchema(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderItemSchema(BaseModel):
    movie_id: int
    price_at_order: Decimal
    model_config = ConfigDict(from_attributes=True)


class OrderResponseSchema(BaseModel):
    id: int
    user_id: int
    status: OrderStatusSchema
    total_amount: Decimal
    created_at: datetime
    items: List[OrderItemSchema]

    model_config = ConfigDict(from_attributes=True)
