# FILE REGISTRY — Enhancement Phases

## Core Files (may be rewritten in any phase if needed)
- manage.py
- config/settings/base.py
- config/settings/local.py
- config/settings/production.py
- config/urls.py
- requirements/base.txt
- requirements/local.txt
- requirements/production.txt
- .env.example

## Per-App Support Files (allowed when necessary)
- {app}/admin.py
- {app}/apps.py
- {app}/managers.py
- {app}/permissions.py
- {app}/tests.py
- {app}/utils.py
- {app}/migrations/__init__.py
- {app}/__init__.py

## Files Modified Per Phase

### Phase 12 — User Profile & Order Tracking
- accounts/models.py (add email field)
- accounts/schemas.py (add ProfileOut, UpdateProfileIn)
- accounts/services.py (add get_profile, update_profile)
- accounts/api.py (add /profile, /orders/my endpoints)
- store/models.py (add tracking_number, postal_tracking to Order)
- store/schemas.py (add OrderTrackingOut, UserOrderListOut)
- accounts/migrations/0004_user_email_order_tracking.py (NEW)
- store/migrations/XXXX_order_tracking_fields.py (NEW)

### Phase 13 — Smart Shipping Calculator
- shipping/models.py (add ShippingZoneRule)
- shipping/schemas.py (add ShippingEstimateIn, ShippingOptionOut)
- shipping/services.py (extend calculate_shipping_cost, add estimate_shipping)
- shipping/api.py (add POST /estimate)
- shipping/admin.py (register ShippingZoneRule)
- shipping/migrations/XXXX_shippingzonerule.py (NEW)

### Phase 14 — Multi-Image Products
- store/models.py (add ProductImage)
- store/schemas.py (add ProductImageOut, update ProductDetailOut)
- store/admin.py (add ProductImageInline to ProductAdmin)
- store/migrations/XXXX_productimage.py (NEW)

### Phase 15 — Blog Publish Fix
- blog/schemas.py (add PostCreateIn, PostUpdateIn, PostAdminOut)
- blog/services.py (add create_post, update_post, publish_post, delete_post)
- blog/api.py (add admin sub-router with CRUD endpoints)

### Phase 16 — Admin Panel API
- admin_panel/__init__.py (NEW)
- admin_panel/apps.py (NEW)
- admin_panel/models.py (NEW — SiteConfig singleton)
- admin_panel/schemas.py (NEW)
- admin_panel/services.py (NEW)
- admin_panel/api.py (NEW)
- admin_panel/admin.py (NEW)
- admin_panel/migrations/ (NEW)
- config/settings/base.py (add admin_panel to INSTALLED_APPS)
- config/urls.py (add admin_panel router)
