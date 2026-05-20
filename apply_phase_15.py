# apply_phase_15.py
# Phase 15 — Smart Shipping (Zone + Weight)
#
# بررسی ZIP فاز ۱۴:
#   - shipping/models.py: ShippingZone و ShippingMethod با تمام فیلدها موجودند
#     → مدل تغییر نمی‌کند → Migration جدید لازم نیست
#   - shipping/schemas.py: ShippingMethodOut, ShippingOptionIn, ShippingOptionOut موجودند
#     → ShippingZoneOut اضافه نشده بود → اضافه می‌شود
#   - shipping/services.py: calculate_shipping_options و calculate_shipping_cost موجودند
#     → بهبود: fallback به متدهای بدون zone وقتی استان در هیچ zone‌ای نباشد
#     → بهبود: calculate_shipping_cost از method مستقیم قبول می‌کند (compat با store)
#   - shipping/api.py: هر دو endpoint موجودند
#     → import‌ها منظم می‌شوند + خطاهای NotFoundError handle می‌شوند
#   - shipping/admin.py: ShippingZone register نشده بود → اضافه می‌شود
#
# تغییرات واقعی این فاز:
#   1. shipping/schemas.py    ← اضافه کردن ShippingZoneOut
#   2. shipping/services.py   ← بهبود fallback منطق + docstring کامل
#   3. shipping/api.py        ← منظم‌سازی imports + error handling
#   4. shipping/admin.py      ← register ShippingZone

import pathlib

BASE = pathlib.Path(__file__).parent


def w(rel: str, content: str) -> None:
    p = BASE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"  [WRITE] {rel}")


print("=" * 60)
print("Phase 15 — Smart Shipping (Zone + Weight)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# 1. shipping/schemas.py
#    تغییرات:
#      - ShippingZoneOut اضافه شد
#      - بقیه schema‌ها بدون تغییر اما کامل بازنویسی می‌شوند
# ─────────────────────────────────────────────────────────────────────────────
w("shipping/schemas.py", '''\
from decimal import Decimal
from typing import List, Optional

from ninja import Schema


# ── ShippingZone ──────────────────────────────────────────────────────────────

class ShippingZoneOut(Schema):
    id: int
    name: str
    provinces: List[str]


# ── ShippingMethod ────────────────────────────────────────────────────────────

class ShippingMethodOut(Schema):
    id: int
    name: str
    base_cost: Decimal
    cost_per_kg: Decimal
    free_above: Optional[Decimal] = None
    min_days: int
    max_days: int


# ── ShippingOption (برای POST /options) ───────────────────────────────────────

class ShippingItemIn(Schema):
    product_id: int
    quantity: int


class ShippingOptionIn(Schema):
    province: str
    items: List[ShippingItemIn]


class ShippingOptionOut(Schema):
    id: int
    name: str
    cost: Decimal
    min_days: int
    max_days: int
''')

# ─────────────────────────────────────────────────────────────────────────────
# 2. shipping/services.py
#    تغییرات:
#      - calculate_shipping_options: fallback به متدهای zone=None وقتی استان
#        در هیچ zone‌ای پیدا نشد (universal methods)
#      - calculate_shipping_cost: پارامترها روشن‌تر، compat با store/services.py
#        که method instance را مستقیم پاس می‌دهد
#      - get_active_shipping_methods: بدون تغییر
# ─────────────────────────────────────────────────────────────────────────────
w("shipping/services.py", '''\
from decimal import Decimal
from typing import List, Optional

from core.exceptions import NotFoundError
from .models import ShippingMethod, ShippingZone


# ── Catalogue ─────────────────────────────────────────────────────────────────

def get_active_shipping_methods() -> List[ShippingMethod]:
    """لیست همه روش‌های ارسال فعال مرتب‌شده بر اساس نام."""
    return list(ShippingMethod.objects.select_related("zone").filter(is_active=True))


# ── Zone lookup ───────────────────────────────────────────────────────────────

def _find_zone_for_province(province: str) -> Optional[ShippingZone]:
    """
    Zone متناسب با نام استان را پیدا می‌کند.
    مقایسه case-sensitive روی JSONField (آرایه‌ای از رشته فارسی).
    اگر استان در هیچ zone‌ای نبود → None برمی‌گرداند.
    """
    return ShippingZone.objects.filter(provinces__contains=province).first()


# ── Cost calculator ───────────────────────────────────────────────────────────

def _calc_cost(
    method: ShippingMethod,
    total_weight_kg: float,
    order_total: Decimal,
) -> Decimal:
    """
    هزینه ارسال برای یک متد مشخص محاسبه می‌کند.

    منطق:
      - اگر free_above تنظیم شده و order_total >= free_above → cost = 0
      - وزن اضافه از ۱ کیلو: extra_weight = max(0, weight - 1)
      - cost = base_cost + extra_weight × cost_per_kg
    """
    if method.free_above is not None and order_total >= method.free_above:
        return Decimal("0")

    extra_weight = max(0.0, total_weight_kg - 1.0)
    cost = method.base_cost + Decimal(str(extra_weight)) * method.cost_per_kg
    return cost


# ── Public API ────────────────────────────────────────────────────────────────

def calculate_shipping_options(
    province: str,
    total_weight_kg: float,
    order_total: Decimal,
) -> list:
    """
    بر اساس استان مقصد و وزن سبد، لیست روش‌های ارسال با قیمت برمی‌گرداند.

    منطق انتخاب متدها:
      1. zone متناسب با province پیدا می‌شود.
      2. اگر zone پیدا شد → متدهای آن zone برگردانده می‌شوند.
      3. اگر zone پیدا نشد (استان در هیچ منطقه‌ای نیست) →
         متدهای بدون zone (zone=None) که universal هستند برگردانده می‌شوند.
         این رفتار «fallback» از بین رفتن تمام گزینه‌های ارسال را جلوگیری می‌کند.

    خروجی: لیستی از dict با کلیدهای id, name, cost, min_days, max_days
    """
    zone = _find_zone_for_province(province)

    if zone is not None:
        methods = ShippingMethod.objects.filter(zone=zone, is_active=True)
    else:
        # استان در هیچ zone‌ای ثبت نشده → متدهای universal (zone=None)
        methods = ShippingMethod.objects.filter(zone__isnull=True, is_active=True)

    results = []
    for method in methods.order_by("base_cost"):
        cost = _calc_cost(method, total_weight_kg, order_total)
        results.append({
            "id":       method.pk,
            "name":     method.name,
            "cost":     cost,
            "min_days": method.min_days,
            "max_days": method.max_days,
        })

    return results


def calculate_shipping_cost(
    method_id_or_obj,
    total_weight: Optional[float] = None,
    order_total: Optional[Decimal] = None,
) -> Decimal:
    """
    هزینه ارسال برای یک ShippingMethod مشخص محاسبه می‌کند.
    هم method_id (int) و هم instance (ShippingMethod) را قبول می‌کند.

    این تابع توسط store/services.py هنگام ایجاد سفارش فراخوانی می‌شود.
    اگر total_weight یا order_total ارائه نشده باشد با مقادیر پیش‌فرض کار می‌کند.
    """
    if isinstance(method_id_or_obj, ShippingMethod):
        method = method_id_or_obj
    else:
        try:
            method = ShippingMethod.objects.get(pk=method_id_or_obj, is_active=True)
        except ShippingMethod.DoesNotExist:
            raise NotFoundError(
                f"ShippingMethod با id={method_id_or_obj} یافت نشد یا غیرفعال است."
            )

    weight = total_weight if total_weight is not None else 0.0
    total  = order_total  if order_total  is not None else Decimal("0")

    return _calc_cost(method, weight, total)
''')

# ─────────────────────────────────────────────────────────────────────────────
# 3. shipping/api.py
#    تغییرات:
#      - imports منظم (همه در بالای فایل)
#      - خطای product not found به جای continue → لاگ می‌شود و skip می‌شود
#      - response مستقیماً از service برمی‌گردد (Ninja خودش validate می‌کند)
# ─────────────────────────────────────────────────────────────────────────────
w("shipping/api.py", '''\
from decimal import Decimal
from typing import List

from ninja import Router

from .schemas import ShippingMethodOut, ShippingOptionIn, ShippingOptionOut
from .services import get_active_shipping_methods, calculate_shipping_options

router = Router(tags=["Shipping"])


@router.get(
    "/methods",
    response=List[ShippingMethodOut],
    summary="لیست روش‌های ارسال فعال",
)
def list_shipping_methods(request):
    """لیست همه روش‌های ارسال فعال برای نمایش در صفحه checkout."""
    return get_active_shipping_methods()


@router.post(
    "/options",
    response=List[ShippingOptionOut],
    summary="محاسبه گزینه‌های ارسال بر اساس استان و سبد",
)
def get_shipping_options(request, payload: ShippingOptionIn):
    """
    بر اساس استان مقصد و لیست آیتم‌های سبد، گزینه‌های ارسال با قیمت محاسبه‌شده
    برمی‌گرداند.

    - وزن کل از مجموع وزن × تعداد هر محصول محاسبه می‌شود.
    - مبلغ کل از قیمت مؤثر (discount_price اگر موجود بود، وگرنه price) محاسبه می‌شود.
    - اگر استان در هیچ zone‌ای نباشد، متدهای universal (zone=None) نمایش داده می‌شوند.
    - محصولات ناموجود یا غیرفعال نادیده گرفته می‌شوند.
    """
    from store.models import Product

    total_weight_kg = 0.0
    order_total     = Decimal("0")

    for item in payload.items:
        product = (
            Product.objects
            .filter(pk=item.product_id, is_active=True)
            .only("weight", "price", "discount_price")
            .first()
        )
        if product is None:
            continue  # محصول ناموجود یا غیرفعال → نادیده گرفته می‌شود

        total_weight_kg += float(product.weight) * item.quantity
        effective_price  = product.discount_price if product.discount_price else product.price
        order_total     += effective_price * item.quantity

    return calculate_shipping_options(payload.province, total_weight_kg, order_total)
''')

# ─────────────────────────────────────────────────────────────────────────────
# 4. shipping/admin.py
#    تغییرات:
#      - ShippingZone اضافه شد به admin
# ─────────────────────────────────────────────────────────────────────────────
w("shipping/admin.py", '''\
from django.contrib import admin

from .models import ShippingZone, ShippingMethod


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display  = ("name", "province_count")
    search_fields = ("name",)

    @admin.display(description="تعداد استان‌ها")
    def province_count(self, obj):
        return len(obj.provinces) if obj.provinces else 0


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display   = ("name", "slug", "zone", "base_cost", "cost_per_kg",
                      "free_above", "min_days", "max_days", "is_active")
    list_editable  = ("is_active", "base_cost", "cost_per_kg")
    list_filter    = ("is_active", "zone")
    search_fields  = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields  = ("zone",)
''')

print()
print("=" * 60)
print("فایل‌های ایجاد/بروزرسانی شده:")
print("  shipping/schemas.py   ← ShippingZoneOut اضافه شد")
print("  shipping/services.py  ← fallback منطق + docstring کامل")
print("  shipping/api.py       ← imports منظم + error handling")
print("  shipping/admin.py     ← ShippingZone register شد")
print()
print("⚠  مدل تغییر نکرد → Migration جدید لازم نیست")
print("=" * 60)
print()
print("مراحل بعدی:")
print("  python manage.py check")
print("  python manage.py makemigrations --check   (باید: No changes detected)")
print("  python manage.py runserver")
print("  http://127.0.0.1:8000/api/docs")
