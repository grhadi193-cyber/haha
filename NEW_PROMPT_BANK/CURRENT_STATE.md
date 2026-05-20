# CURRENT STATE

## Completed Phases (base project)
- [x] Phase 01 — Bootstrap (project skeleton, settings, requirements)
- [x] Phase 02 — Core (exceptions, base API router, health endpoint)
- [x] Phase 03 — SMS (Kavenegar integration, send_otp service)
- [x] Phase 04 — Accounts & User (custom User model, Address model)
- [x] Phase 05 — OTP Auth (OTPRecord, send-otp, verify-otp, JWT)
- [x] Phase 06 — Store Catalog (Category, Product, list/detail endpoints)
- [x] Phase 07 — Shipping (ShippingMethod, list endpoint, calculate_shipping_cost)
- [x] Phase 08 — Orders (Order, OrderItem, create_order service, POST /orders)
- [x] Phase 09 — Payment (Transaction, ZarinPal gateway, payment callback)
- [x] Phase 10 — Blog (Post model, published list/detail endpoints)
- [x] Phase 11 — Hardening & Deploy (production settings, whitenoise, CORS, logging)

## Enhancement Phases (new)
- [x] Phase 12 — User Profile & Order Tracking
- [ ] Phase 13 — Smart Shipping Calculator
- [ ] Phase 14 — Multi-Image Products
- [ ] Phase 15 — Blog Publish Fix
- [ ] Phase 16 — Admin Panel API

## Next Phase
Phase 13

## Changes in Phase 12
- accounts.User: email field added (EmailField, blank=True, default="")
- store.Order: tracking_number + postal_tracking fields added
- tracking_number auto-generated as ORD-{id:06d} on first save
- New endpoints: GET/PATCH /api/auth/profile, GET /api/auth/orders, GET /api/auth/orders/{id}
- Status Persian labels returned via STATUS_DISPLAY dict in store/schemas.py
- get_user_orders, get_user_order_detail added to store/services.py
- get_profile, update_profile added to accounts/services.py

## Known Issues (remaining)
- shipping: calculate_shipping_cost uses only base_cost, weight/city hooks exist but unimplemented
- store.Product: only single image field
- blog: POST to create/publish posts not exposed via API — only readable via admin
- no dedicated admin API (only Django admin UI)
