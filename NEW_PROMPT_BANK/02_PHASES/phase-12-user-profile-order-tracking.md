# PHASE 12 — User Profile & Order Tracking

## Goal
Give users their own profile page and full order history with real-time status tracking.

## Context
- accounts.User currently has: phone_number, full_name, is_active, is_staff
- store.Order currently has: user, address, shipping_method, status, total_price, shipping_cost, created_at
- Status choices (already in model): pending, paid, processing, shipped, delivered, cancelled
- Auth: JWT Bearer (AuthBearer pattern from store/api.py — reuse exactly)

## Deliverables

### accounts/models.py (update)
Add to User model:
- email = models.EmailField(blank=True, default="")

### accounts/schemas.py (update)
Add:
- ProfileOut: phone_number, full_name, email
- UpdateProfileIn: full_name (optional), email (optional)

### accounts/services.py (update)
Add:
- get_profile(user) -> User
- update_profile(user, full_name: str | None, email: str | None) -> User

### accounts/api.py (update)
Add (auth required with AuthBearer):
- GET /api/auth/profile → ProfileOut
- PATCH /api/auth/profile → UpdateProfileIn → ProfileOut

### store/models.py (update)
Add to Order model:
- tracking_number = CharField(max_length=64, blank=True, default="")
  (internal order reference, auto-generated on create as "ORD-{id:06d}")
- postal_tracking = CharField(max_length=64, blank=True, default="")
  (Iran Post tracking number, filled by admin when shipped)

### store/schemas.py (update)
Add:
- OrderItemTrackingOut: product_name, quantity, unit_price
- UserOrderOut: id, tracking_number, postal_tracking, status, status_display (Persian),
                total_price, shipping_cost, created_at, items (list of OrderItemTrackingOut)

### accounts/api.py (also add):
- GET /api/auth/orders → List[UserOrderOut]  (all orders for logged-in user, newest first)
- GET /api/auth/orders/{order_id} → UserOrderOut  (single order, must belong to user)

### Status Display Map (Persian, in service layer)
```
STATUS_DISPLAY = {
    "pending":    "درحال تایید",
    "paid":       "تایید شده",
    "processing": "آماده سازی",
    "shipped":    "تحویل به پست",
    "delivered":  "تحویل داده شده",
    "cancelled":  "لغو شده",
}
```

### Migrations Required
- accounts/migrations/0004_user_email.py
- store/migrations/000X_order_tracking_fields.py
  (check existing migrations to determine correct number)

## Target Files
- accounts/models.py
- accounts/schemas.py
- accounts/services.py
- accounts/api.py
- store/models.py
- store/schemas.py
- accounts/migrations/0004_user_email.py
- store/migrations/000X_order_tracking_fields.py

## Acceptance Criteria
- makemigrations + migrate OK
- GET /api/auth/profile → 200 with user data (requires JWT)
- PATCH /api/auth/profile with {"full_name": "علی رضایی"} → 200, updated
- GET /api/auth/orders → 200, list of user orders (empty list if none)
- GET /api/auth/orders/1 → 200 with tracking info OR 404 if not user's order
- status_display returns correct Persian label
- tracking_number format: "ORD-000001"
- Swagger shows all 4 new endpoints under Auth tag
