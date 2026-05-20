# PHASE 16 — Admin Panel API

## Goal
Full headless admin API so site operators can manage everything without Django admin UI.
Every endpoint requires staff JWT (is_staff=True).

## Context
- All models exist: User (accounts), Product/Order/OrderItem (store), ShippingMethod (shipping)
- Order status choices: pending, paid, processing, shipped, delivered, cancelled
- Order has tracking_number and postal_tracking (added in phase 12)
- AdminBearer pattern established in phase 15 (blog/api.py) — replicate here

## Deliverables

### New App: admin_panel

#### admin_panel/__init__.py
empty

#### admin_panel/apps.py
```python
from django.apps import AppConfig
class AdminPanelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "admin_panel"
    verbose_name = "پنل مدیریت"
```

#### admin_panel/models.py
SiteConfig singleton:
```python
class SiteConfig(models.Model):
    announcement      = models.TextField(blank=True, default="")
    banner_text       = models.CharField(max_length=255, blank=True, default="")
    maintenance_mode  = models.BooleanField(default=False)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات سایت"

    def __str__(self):
        return "Site Configuration"

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

#### admin_panel/schemas.py
Define all input/output schemas:

```
AdminUserOut: id, phone_number, full_name, email, is_active, is_staff, date_joined
AdminUserUpdateIn: full_name (opt), is_active (opt), is_staff (opt)

AdminProductListOut: id, name, slug, price, stock, is_active, category_id, weight
AdminProductCreateIn: name, slug, description, price, stock, weight, category_id (opt), is_active
AdminProductUpdateIn: all fields optional

AdminInventoryOut: id, name, stock
AdminInventoryUpdateIn: stock (int >=0)

AdminOrderListOut: id, tracking_number, postal_tracking, user_phone, status, total_price, created_at
AdminOrderStatusUpdateIn: status (str), postal_tracking (optional str)

SalesStatsOut: total_orders (int), total_revenue (Decimal), orders_by_status (dict), top_products (list)
TopProductOut: product_id, product_name, units_sold, revenue

SiteConfigOut: announcement, banner_text, maintenance_mode, updated_at
SiteConfigUpdateIn: announcement (opt), banner_text (opt), maintenance_mode (opt)
```

#### admin_panel/services.py
All service functions (no HttpRequest):
```
# Users
list_users() -> list[User]
get_user(user_id) -> User
update_user(user_id, **kwargs) -> User

# Products
list_all_products() -> list[Product]
create_product(**kwargs) -> Product
update_product(product_id, **kwargs) -> Product
delete_product(product_id) -> None

# Inventory
list_inventory() -> list[Product]  (id, name, stock only)
update_stock(product_id, stock) -> Product

# Orders
list_all_orders() -> list[Order]  (select_related user, prefetch items)
update_order_status(order_id, status, postal_tracking=None) -> Order
get_sales_stats() -> dict
  - total_orders: count of orders in last 30 days
  - total_revenue: sum of total_price for paid/processing/shipped/delivered in last 30 days
  - orders_by_status: {status: count} for all time
  - top_products: top 5 products by units_sold (last 30 days)

# Site Config
get_site_config() -> SiteConfig
update_site_config(**kwargs) -> SiteConfig
```

#### admin_panel/api.py
AdminBearer class (same as phase 15 pattern, checks is_staff).
All routes under single router, tags=["Admin Panel"]:

```
GET    /api/admin/users                     → list AdminUserOut
GET    /api/admin/users/{user_id}           → AdminUserOut
PATCH  /api/admin/users/{user_id}           → AdminUserUpdateIn → AdminUserOut

GET    /api/admin/products                  → list AdminProductListOut
POST   /api/admin/products                  → AdminProductCreateIn → AdminProductListOut
PATCH  /api/admin/products/{product_id}     → AdminProductUpdateIn → AdminProductListOut
DELETE /api/admin/products/{product_id}     → 204

GET    /api/admin/inventory                 → list AdminInventoryOut
PATCH  /api/admin/inventory/{product_id}    → AdminInventoryUpdateIn → AdminInventoryOut

GET    /api/admin/orders                    → list AdminOrderListOut
PATCH  /api/admin/orders/{order_id}/status  → AdminOrderStatusUpdateIn → AdminOrderListOut
GET    /api/admin/orders/stats              → SalesStatsOut

GET    /api/admin/site-config               → SiteConfigOut
PATCH  /api/admin/site-config               → SiteConfigUpdateIn → SiteConfigOut
```

#### admin_panel/admin.py
Register SiteConfig with:
- list_display = ("maintenance_mode", "banner_text", "updated_at")

#### admin_panel/migrations/0001_initial.py
Migration for SiteConfig model.

### config/settings/base.py (update)
Add "admin_panel" to INSTALLED_APPS.

### config/urls.py (update)
```python
from admin_panel.api import router as admin_panel_router
api.add_router("/admin", admin_panel_router)
```

## Target Files
- admin_panel/__init__.py (NEW)
- admin_panel/apps.py (NEW)
- admin_panel/models.py (NEW)
- admin_panel/schemas.py (NEW)
- admin_panel/services.py (NEW)
- admin_panel/api.py (NEW)
- admin_panel/admin.py (NEW)
- admin_panel/migrations/__init__.py (NEW)
- admin_panel/migrations/0001_initial.py (NEW)
- config/settings/base.py (update INSTALLED_APPS)
- config/urls.py (add router)

## Acceptance Criteria
- makemigrations + migrate OK
- GET /api/admin/users without token → 401
- GET /api/admin/users with non-staff JWT → 401
- GET /api/admin/users with staff JWT → 200, list of users
- POST /api/admin/products → creates product, returns it
- PATCH /api/admin/orders/1/status {"status": "shipped", "postal_tracking": "1234567890"} → 200
- GET /api/admin/orders/stats → returns totals and top_products list
- GET /api/admin/site-config → 200 with config
- PATCH /api/admin/site-config {"maintenance_mode": true} → updated
- GET /api/admin/inventory → list with stock numbers
- PATCH /api/admin/inventory/1 {"stock": 50} → stock updated
- Swagger shows all admin endpoints under "Admin Panel" tag
- Django /admin shows SiteConfig
