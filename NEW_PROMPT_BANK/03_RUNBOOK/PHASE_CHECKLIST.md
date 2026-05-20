# PHASE CHECKLIST SUMMARY — Enhancement Phases

## Phase 12 — User Profile & Order Tracking
- [ ] email field added to User model
- [ ] tracking_number and postal_tracking added to Order model
- [ ] GET /api/auth/profile works with JWT
- [ ] PATCH /api/auth/profile updates name/email
- [ ] GET /api/auth/orders returns user's orders with Persian status labels
- [ ] GET /api/auth/orders/{id} returns single order (404 if not owned)

## Phase 13 — Smart Shipping Calculator
- [ ] ShippingZoneRule model created and migrated
- [ ] POST /api/shipping/estimate returns multiple options
- [ ] Cost = base_cost + (weight × price_per_kg) for matching zone rule
- [ ] Existing calculate_shipping_cost(method_id) still works
- [ ] Admin can manage ShippingZoneRule

## Phase 14 — Multi-Image Products
- [ ] ProductImage model created and migrated
- [ ] GET /api/products/{id} includes images list with full URLs
- [ ] GET /api/products list not affected
- [ ] Admin product page shows gallery inline
- [ ] Original Product.image field unchanged

## Phase 15 — Blog Publish Fix
- [ ] POST /api/blog/admin/posts creates post
- [ ] PATCH with is_published=true sets published_at=now
- [ ] DELETE removes post
- [ ] Non-staff JWT → 401 on admin endpoints
- [ ] Public GET /api/blog/posts unaffected
- [ ] No migration needed

## Phase 16 — Admin Panel API
- [ ] admin_panel app created with SiteConfig model
- [ ] All user management endpoints working
- [ ] All product management endpoints working
- [ ] Inventory endpoint working
- [ ] Order status update with postal_tracking working
- [ ] Sales stats returning correct data
- [ ] SiteConfig get/patch working
- [ ] All endpoints 401 for non-staff
- [ ] Swagger shows "Admin Panel" tag with all endpoints
