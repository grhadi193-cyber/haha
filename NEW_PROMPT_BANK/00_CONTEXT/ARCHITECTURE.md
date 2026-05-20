# ARCHITECTURE — Enhancement Phases (12–16)

## Stack (unchanged)
- Django (latest stable)
- Django Ninja + Pydantic v2
- PostgreSQL
- django-environ, simplejwt, kavenegar, az-iranian-bank-gateways, whitenoise, corsheaders

## Style (unchanged)
- API-only / Headless
- Service Layer architecture
- No Django Signals
- models.py: thin, no business logic
- schemas.py: strict I/O contracts via Pydantic v2
- services.py: all logic, NO HttpRequest dependency
- api.py: receive → validate → call service → return JSON

## Existing Apps
core → sms → accounts → store → shipping → payment → blog

## Key Existing Models
- accounts.User: phone_number, full_name, is_active, is_staff
- accounts.Address: user FK, province, city, street, postal_code, is_default
- store.Product: name, slug, price, stock, weight (Decimal), image, category FK
- store.Order: user FK, address FK, shipping_method FK, status (pending/paid/processing/shipped/delivered/cancelled), total_price, shipping_cost, created_at
- store.OrderItem: order FK, product FK, quantity, unit_price
- shipping.ShippingMethod: name, slug, base_cost, is_active
- payment.Transaction: order FK, amount, ref_id, status, gateway_response
- blog.Post: title, slug, content, featured_image, published_at, is_published

## Auth Pattern
- JWT Bearer token via simplejwt
- AuthBearer class in store/api.py (reuse pattern in new apps/routers)
- Admin endpoints: is_staff=True check inside service or via custom bearer

## Error Handling
- All custom exceptions in core/exceptions.py
- All API errors return structured JSON
- No raw 500 in production

## New Apps to Build (phases 12–16)
- No new top-level apps needed
- Changes extend existing apps + add admin_panel app (phase 16)
