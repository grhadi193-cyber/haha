# DECISIONS

## Enhancement Phase Decisions

### Phase 12 — User Profile & Order Tracking
- User can update full_name and email via PATCH /api/auth/profile
- email field added to accounts.User (optional, blank=True)
- Order tracking via GET /api/orders/my — returns all orders of authenticated user
- Order detail via GET /api/orders/my/{order_id} — includes tracking_number and postal_tracking fields
- tracking_number and postal_tracking added to store.Order model
- Status labels in Persian returned via a computed field (not stored)
- Status Persian map: pending→درحال تایید, paid→تایید شده, processing→آماده سازی, shipped→تحویل به پست, delivered→تحویل داده شده, cancelled→لغو شده

### Phase 13 — Smart Shipping Calculator
- New endpoint: POST /api/shipping/estimate
  - Input: product_ids (list), destination_province, destination_city
  - Returns: list of ShippingOptionOut (method_id, name, cost, estimated_days, advantage)
- Origin is always Mashhad (hardcoded in service)
- Weight pulled from Product.weight per item, summed for cart
- Cost = base_cost + weight_surcharge (tiers defined in ShippingZoneRule model)
- ShippingZoneRule model: origin_province, destination_province, method FK, price_per_kg, estimated_days
- advantage field per method: short label describing the benefit (e.g. "سریع‌ترین", "مقرون‌به‌صرفه")
- calculate_shipping_cost in shipping/services.py extended (backward-compatible signature)

### Phase 14 — Multi-Image Products
- New model: store.ProductImage (product FK, image, alt_text, order)
- ProductDetailOut extended with images: list[ProductImageOut]
- Existing store.Product.image field kept (primary/legacy image)
- ProductImage.order field (PositiveSmallIntegerField) controls display order
- Admin: ProductImageInline inside ProductAdmin (TabularInline)

### Phase 15 — Blog Publish Fix
- Blog POST creation and publish exposed as admin-only API endpoints
- POST /api/blog/admin/posts — create post
- PATCH /api/blog/admin/posts/{id} — update + publish (set is_published=True, published_at=now)
- DELETE /api/blog/admin/posts/{id} — delete post
- Uses AdminBearer (is_staff=True check), same pattern as phase 16
- Root cause of publish bug: is_published was never set to True via API — only Django admin
- Services: create_post, update_post, publish_post, delete_post in blog/services.py

### Phase 16 — Admin Panel API
- New app: admin_panel
- AdminBearer: custom HttpBearer that checks user.is_staff == True
- Endpoints grouped under /api/admin/
  - Users: GET /users, GET /users/{id}, PATCH /users/{id}
  - Products: GET /products, POST /products, PATCH /products/{id}, DELETE /products/{id}
  - Inventory: GET /inventory, PATCH /inventory/{product_id} (update stock)
  - Orders: GET /orders (all), PATCH /orders/{id}/status, GET /orders/stats
  - Site Config: GET /site-config, PATCH /site-config (banner text, announcement, maintenance mode)
- SiteConfig: singleton model (only one row), stored in admin_panel app
- Sales stats endpoint returns: total_orders, total_revenue, orders_by_status, top_products (last 30 days)
