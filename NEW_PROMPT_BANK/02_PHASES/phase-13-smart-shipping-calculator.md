# PHASE 13 — Smart Shipping Calculator

## Goal
Real-time shipping cost estimation based on product weight, destination city/province,
with multiple shipping options shown with their advantages.

## Context
- shipping.ShippingMethod: id, name, slug, base_cost (Decimal), is_active
- shipping.services.calculate_shipping_cost(method_id, total_weight=None) — currently returns base_cost only
- store.Product has weight (Decimal, kg) field
- Origin is ALWAYS Mashhad, Khorasan Razavi (hardcoded constant)
- Must remain backward-compatible: calculate_shipping_cost(method_id) still works

## Deliverables

### shipping/models.py (update)
Add ShippingZoneRule model:
- method = ForeignKey(ShippingMethod, on_delete=CASCADE, related_name="zone_rules")
- destination_province = CharField(max_length=100)
  (use Persian province names, e.g. "تهران", "اصفهان", "خراسان رضوی")
- price_per_kg = DecimalField(max_digits=10, decimal_places=0, default=0)
  (extra cost per kg above base_cost)
- estimated_days = PositiveSmallIntegerField(default=3)
- advantage = CharField(max_length=128, blank=True, default="")
  (short Persian label, e.g. "سریع‌ترین", "مقرون‌به‌صرفه", "با ردیابی پستی")

  class Meta:
    unique_together = [("method", "destination_province")]
    ordering = ["method__name"]

### shipping/schemas.py (update)
Add:
- ShippingEstimateIn: product_ids (list[int]), destination_province (str), destination_city (str)
- ShippingOptionOut: method_id (int), method_name (str), cost (Decimal),
                     estimated_days (int), advantage (str)

### shipping/services.py (update)
- ORIGIN_PROVINCE = "خراسان رضوی" (module-level constant)
- Keep existing calculate_shipping_cost(method_id, total_weight=None) signature
- Extend it: if total_weight provided and ShippingZoneRule exists → cost += weight * price_per_kg

Add:
- estimate_shipping(product_ids: list[int], destination_province: str, destination_city: str)
    -> list[ShippingOptionOut]
  Logic:
  1. Fetch Products by ids, sum weights → total_weight_kg
  2. Fetch all active ShippingMethods
  3. For each method: look up ShippingZoneRule for (method, destination_province)
     - If rule found: cost = method.base_cost + (total_weight * rule.price_per_kg)
                      estimated_days = rule.estimated_days
                      advantage = rule.advantage
     - If no rule: cost = method.base_cost, estimated_days = 5, advantage = ""
  4. Return sorted list (cheapest first)

### shipping/api.py (update)
Add:
- POST /api/shipping/estimate → ShippingEstimateIn → List[ShippingOptionOut]
  (no auth required — public endpoint)

### shipping/admin.py (update)
Register ShippingZoneRule with:
- list_display = ("method", "destination_province", "price_per_kg", "estimated_days", "advantage")
- list_filter = ("method",)

### Migration Required
- shipping/migrations/0002_shippingzonerule.py

## Target Files
- shipping/models.py
- shipping/schemas.py
- shipping/services.py
- shipping/api.py
- shipping/admin.py
- shipping/migrations/0002_shippingzonerule.py

## Acceptance Criteria
- makemigrations + migrate OK
- POST /api/shipping/estimate with {"product_ids": [1], "destination_province": "تهران", "destination_city": "تهران"}
  → 200, list of shipping options with cost and advantage
- Each option shows: method_id, method_name, cost (number), estimated_days, advantage
- Existing GET /api/shipping/methods still works unchanged
- calculate_shipping_cost(1) still works (no weight arg) → returns base_cost
- calculate_shipping_cost(1, total_weight=2.5) → returns base_cost + surcharge
- Swagger shows POST /estimate endpoint
- Admin: ShippingZoneRule visible and editable
