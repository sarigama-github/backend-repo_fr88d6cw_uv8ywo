import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Restaurant, MenuItem, Order, OrderItem

app = FastAPI(title="Food Delivery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


@app.get("/")
def root():
    return {"message": "Food Delivery API Running"}


# Auth (basic email/password demo only - not production secure)
@app.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest):
    existing = db["user"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=payload.password,  # NOTE: demo only (would hash in prod)
        is_admin=False,
    )
    user_id = create_document("user", user)
    token = str(ObjectId())
    db["user"].update_one({"_id": oid(user_id)}, {"$push": {"tokens": token}})
    created = db["user"].find_one({"_id": oid(user_id)})
    created["_id"] = str(created["_id"])
    return {"token": token, "user": created}


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    user = db["user"].find_one({"email": payload.email})
    if not user or user.get("password_hash") != payload.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = str(ObjectId())
    db["user"].update_one({"_id": user["_id"]}, {"$push": {"tokens": token}})
    user["_id"] = str(user["_id"])
    return {"token": token, "user": user}


# Seed sample restaurants if empty
@app.post("/admin/seed")
def seed():
    if db["restaurant"].count_documents({}) == 0:
        samples = [
            Restaurant(
                name="Saffron Palace",
                image_url="https://images.unsplash.com/photo-1544025162-d76694265947",
                cuisine=["Indian", "Curry"],
                rating=4.7,
                delivery_time_min=25,
                delivery_time_max=45,
                description="Authentic Indian cuisine with rich flavors.",
            ).model_dump(),
            Restaurant(
                name="Green Bowl",
                image_url="https://images.unsplash.com/photo-1556910103-1c02745aae4d",
                cuisine=["Healthy", "Salads"],
                rating=4.6,
                delivery_time_min=15,
                delivery_time_max=30,
                description="Fresh bowls and salads.",
            ).model_dump(),
            Restaurant(
                name="Bella Pasta",
                image_url="https://images.unsplash.com/photo-1523986371872-9d3ba2e2b1a9",
                cuisine=["Italian", "Pasta"],
                rating=4.8,
                delivery_time_min=30,
                delivery_time_max=50,
                description="Classic Italian pasta and more.",
            ).model_dump(),
        ]
        db["restaurant"].insert_many(samples)

    # Seed menu items per restaurant
    for r in db["restaurant"].find({}):
        if db["menuitem"].count_documents({"restaurant_id": str(r["_id"])}) == 0:
            items = [
                MenuItem(
                    restaurant_id=str(r["_id"]),
                    name="Margherita Pizza",
                    description="Classic with fresh mozzarella and basil",
                    price=12.99,
                    image_url="https://images.unsplash.com/photo-1548365328-9f547fb0953d",
                    tags=["vegetarian"],
                ).model_dump(),
                MenuItem(
                    restaurant_id=str(r["_id"]),
                    name="Spicy Paneer Bowl",
                    description="Paneer with spicy sauce and rice",
                    price=10.5,
                    image_url="https://images.unsplash.com/photo-1544025162-d76694265947",
                    tags=["spicy"],
                ).model_dump(),
            ]
            db["menuitem"].insert_many(items)
    return {"status": "ok"}


# Restaurants
@app.get("/restaurants")
def list_restaurants(q: Optional[str] = None, cuisine: Optional[str] = None, min_rating: float = 0):
    query = {}
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    if cuisine:
        query["cuisine"] = cuisine
    if min_rating:
        query["rating"] = {"$gte": float(min_rating)}

    docs = list(db["restaurant"].find(query))
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


@app.get("/restaurants/{restaurant_id}")
def get_restaurant(restaurant_id: str):
    r = db["restaurant"].find_one({"_id": oid(restaurant_id)})
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    r["_id"] = str(r["_id"])
    return r


@app.get("/restaurants/{restaurant_id}/menu")
def get_menu(restaurant_id: str):
    items = list(db["menuitem"].find({"restaurant_id": restaurant_id, "is_available": True}))
    for i in items:
        i["_id"] = str(i["_id"])
    return items


# Orders
class CreateOrderRequest(BaseModel):
    user_id: str
    restaurant_id: str
    items: List[OrderItem]
    delivery_address: Optional[str] = None
    notes: Optional[str] = None
    payment_method: str = "card"


@app.post("/orders")
def create_order(payload: CreateOrderRequest):
    # compute totals
    subtotal = sum(i.price * i.quantity for i in payload.items)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)
    order = Order(
        user_id=payload.user_id,
        restaurant_id=payload.restaurant_id,
        items=payload.items,
        subtotal=subtotal,
        tax=tax,
        total=total,
        payment_method=payload.payment_method,  # demo: treat as paid
        payment_status="paid",
        delivery_address=payload.delivery_address,
        notes=payload.notes,
    )
    order_id = create_document("order", order)
    return {"order_id": order_id, "status": "confirmed", "total": total}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    o = db["order"].find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Not found")
    o["_id"] = str(o["_id"])
    return o


@app.get("/orders/{order_id}/status")
def order_status(order_id: str):
    o = db["order"].find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": o.get("status", "confirmed")}


@app.post("/orders/{order_id}/advance")
def advance_status(order_id: str):
    # For demo: cycle through statuses
    o = db["order"].find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Not found")
    flow = ["confirmed", "preparing", "out_for_delivery", "delivered"]
    cur = o.get("status", "confirmed")
    try:
        nxt = flow[flow.index(cur) + 1]
    except Exception:
        nxt = "delivered"
    db["order"].update_one({"_id": o["_id"]}, {"$set": {"status": nxt}})
    return {"status": nxt}


# Admin simple endpoints
class MenuItemPayload(BaseModel):
    restaurant_id: str
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    is_available: bool = True


@app.post("/admin/menu")
def add_menu_item(payload: MenuItemPayload):
    item = MenuItem(**payload.model_dump())
    item_id = create_document("menuitem", item)
    return {"item_id": item_id}


class UpdateMenuItemPayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None


@app.patch("/admin/menu/{item_id}")
def update_menu_item(item_id: str, payload: UpdateMenuItemPayload):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    db["menuitem"].update_one({"_id": oid(item_id)}, {"$set": updates})
    return {"status": "ok"}


@app.get("/admin/orders")
def admin_orders(restaurant_id: Optional[str] = None):
    query = {"restaurant_id": restaurant_id} if restaurant_id else {}
    docs = list(db["order"].find(query))
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
