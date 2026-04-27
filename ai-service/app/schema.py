from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Role = Literal["ADMIN", "CORPORATE", "INDIVIDUAL"]
Status = Literal["ANSWER", "GREETING", "OUT_OF_SCOPE", "BLOCKED"]
Classification = Literal["greeting", "in_scope", "out_of_scope", "prompt_injection", "cross_tenant", "sql_injection"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., max_length=1000)
    user_id: int
    role: Role
    store_owner_id: Optional[int] = None
    first_name: Optional[str] = None
    history: List[ChatTurn] = []


class DataRow(BaseModel):
    label: str
    value: float


class TableData(BaseModel):
    columns: List[str]
    rows: List[List[object]]


class Guardrail(BaseModel):
    type: str
    trigger: str
    action: str


class ChatResponse(BaseModel):
    status: Status
    narrative: str
    title: Optional[str] = None
    bullets: Optional[List[str]] = None
    insight: Optional[str] = None
    sql_preview: Optional[str] = None
    rows: Optional[List[DataRow]] = None
    chart_type: Optional[Literal["BAR", "LINE", "PIE", "NONE"]] = None
    table: Optional[TableData] = None
    guardrail: Optional[Guardrail] = None


# Static schema doc passed to the SQL agent — never live introspection.
# Sensitive columns (password_hash, refresh_tokens, email_verification_*, stripe_*)
# are deliberately omitted.
DB_SCHEMA_DOC = """
Tables (MySQL 8):

users(id, email, first_name, last_name, role['ADMIN'|'CORPORATE'|'INDIVIDUAL'],
      gender, phone, created_at, enabled)
stores(id, owner_id -> users.id, name, status['PENDING_APPROVAL'|'OPEN'|'SUSPENDED'|'CLOSED'], created_at)
categories(id, name, parent_id -> categories.id)
products(id, store_id -> stores.id, category_id -> categories.id, sku, name,
         description, unit_price, stock_quantity, image_url, active, created_at, updated_at)
orders(id, user_id -> users.id, store_id -> stores.id, status, grand_total,
       payment_method, shipping_address, sales_channel, created_at, updated_at)
order_items(id, order_id -> orders.id, product_id -> products.id, quantity, price, discount_applied)
shipments(id, order_id -> orders.id, tracking_id, carrier, warehouse_block, mode_of_shipment,
          destination, status, estimated_delivery, shipped_at, delivered_at, created_at)
reviews(id, user_id -> users.id, product_id -> products.id, star_rating,
        review_body, sentiment, helpful_votes, total_votes, created_at)
customer_profiles(id, user_id -> users.id, age, city, membership_type)
addresses(id, user_id -> users.id, street, city, region, country, is_default)

Conventions:
- Money fields are DECIMAL.
- All timestamps are MySQL DATETIME.
- order.status values: 'PENDING','CONFIRMED','PROCESSING','SHIPPED','DELIVERED','CANCELLED','RETURNED'.
- shipment.status values: 'PENDING','PROCESSING','IN_TRANSIT','DELIVERED','RETURNED'.
- order line revenue = order_items.price * order_items.quantity. There is no oi.unit_price.
- reviews body column is named review_body (not body).
- review.star_rating is 1..5.
""".strip()
