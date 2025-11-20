"""
Database Schemas for Food Delivery App

Each Pydantic model represents a collection in MongoDB. Collection name is the lowercase of the class name.

- User -> "user"
- Restaurant -> "restaurant"
- MenuItem -> "menuitem"
- Order -> "order"
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: Optional[str] = Field(None, description="SHA256 hash of password (or None for social) ")
    avatar_url: Optional[str] = Field(None)
    is_admin: bool = Field(False, description="Is restaurant/admin user")
    provider: Optional[str] = Field(None, description="Social login provider if any")
    provider_id: Optional[str] = Field(None, description="Social provider unique id")
    tokens: Optional[List[str]] = Field(default_factory=list, description="Active auth tokens")


class Restaurant(BaseModel):
    name: str
    image_url: Optional[str] = None
    cuisine: List[str] = Field(default_factory=list)
    rating: float = Field(4.5, ge=0, le=5)
    delivery_time_min: int = Field(20, ge=0)
    delivery_time_max: int = Field(40, ge=0)
    description: Optional[str] = None
    address: Optional[str] = None


class MenuItem(BaseModel):
    restaurant_id: str = Field(..., description="Reference to restaurant _id as string")
    name: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    image_url: Optional[str] = None
    is_available: bool = Field(True)
    tags: List[str] = Field(default_factory=list)


class OrderItem(BaseModel):
    item_id: str
    name: str
    price: float
    quantity: int = Field(1, ge=1)


class Order(BaseModel):
    user_id: str
    restaurant_id: str
    items: List[OrderItem]
    subtotal: float
    tax: float
    total: float
    status: Literal[
        "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"
    ] = "confirmed"
    payment_method: Literal["card", "paypal"] = "card"
    payment_status: Literal["pending", "paid", "failed"] = "paid"
    delivery_address: Optional[str] = None
    notes: Optional[str] = None
