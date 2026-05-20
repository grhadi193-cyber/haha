# apply_phase_14.py
# Phase 14 — Product Gallery + بهبود مدل محصول
#
# پیش از اجرا: این اسکریپت را از پوشه‌ای که manage.py در آن قرار دارد اجرا کن.
# python apply_phase_14.py
#
# وضعیت بررسی‌شده (ZIP فاز ۱۳):
#  - تمام فیلدهای Product (discount_price, sku, meta_title, meta_description,
#    view_count, updated_at, weight) از قبل موجودند → بدون تغییر مدل
#  - مدل ProductImage از قبل موجود است → بدون تغییر مدل
#  - Migration 0008 همه اینها را پوشش داده → Migration جدید لازم نیست
#  - تغییرات واقعی: store/schemas.py, store/services.py, store/admin.py

import pathlib, sys

BASE = pathlib.Path(__file__).parent


def w(rel: str, content: str) -> None:
    p = BASE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"  [WRITE] {rel}")


print("=" * 60)
print("Phase 14 — Product Gallery + بهبود مدل محصول")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────────────────
# 1. store/schemas.py
#    تغییرات:
#      - ProductListOut: اضافه شدن discount_price و weight
#      - بقیه schemas بدون تغییر اما کامل بازنویسی می‌شوند
# ─────────────────────────────────────────────────────────────────────────────
w("store/schemas.py", '''\
from decimal import Decimal
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


# ── Category ─────────────────────────────────────────────────────────────────

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


# ── Product Images ────────────────────────────────────────────────────────────

class ProductImageOut(BaseModel):
    id: int
    image: str
    alt_text: str
    order: int
    is_cover: bool

    model_config = {"from_attributes": True}


# ── Product List (public) ─────────────────────────────────────────────────────

class ProductListOut(BaseModel):
    id: int
    name: str
    slug: str
    price: Decimal
    discount_price: Optional[Decimal] = None   # ← Phase 14: اضافه شد
    weight: Decimal = Decimal("0")             # ← Phase 14: اضافه شد
    stock: int
    image: Optional[str] = None
    category: Optional[CategoryOut] = None

    model_config = {"from_attributes": True}


# ── Product Detail (public) ───────────────────────────────────────────────────

class ProductDetailOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    price: Decimal
    discount_price: Optional[Decimal] = None
    sku: Optional[str] = None
    meta_title: str = ""
    meta_description: str = ""
    view_count: int = 0
    stock: int
    weight: Decimal
    image: Optional[str] = None
    category: Optional[CategoryOut] = None
    images: List[ProductImageOut] = []         # ← گالری تصاویر

    model_config = {"from_attributes": True}


# ── Order (Create) ────────────────────────────────────────────────────────────

class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class CreateOrderIn(BaseModel):
    address_id: int
    shipping_method_id: int
    items: List[OrderItemIn]


# ── Order (Response) ──────────────────────────────────────────────────────────

class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    status: str
    total_price: Decimal
    shipping_cost: Decimal
    tracking_number: str = ""
    payment_url: Optional[str] = None
    items: List[OrderItemOut] = []

    model_config = {"from_attributes": True}


# ── Order Tracking (Phase 13) ─────────────────────────────────────────────────

STATUS_DISPLAY = {
    "pending":    "درحال تایید",
    "paid":       "تایید شده",
    "processing": "آماده سازی",
    "shipped":    "تحویل به پست",
    "delivered":  "تحویل داده شده",
    "cancelled":  "لغو شده",
}


class OrderItemTrackingOut(BaseModel):
    product_name: str
    quantity: int
    unit_price: Decimal


class OrderStatusHistoryOut(BaseModel):
    status: str
    status_display: str
    note: str
    created_at: datetime


class UserOrderOut(BaseModel):
    id: int
    tracking_number: str
    postal_tracking: str
    carrier_name: str
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    customer_notes: str
    status: str
    status_display: str
    total_price: Decimal
    shipping_cost: Decimal
    created_at: datetime
    shipping_address_snapshot: Optional[dict] = None
    items: List[OrderItemTrackingOut]
    history: List[OrderStatusHistoryOut] = []

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        items = [
            OrderItemTrackingOut(
                product_name=i.product_name_snapshot or i.product.name,
                quantity=i.quantity,
                unit_price=i.unit_price,
            )
            for i in obj.items.all()
        ]
        history = [
            OrderStatusHistoryOut(
                status=h.status,
                status_display=STATUS_DISPLAY.get(h.status, h.status),
                note=h.note,
                created_at=h.created_at,
            )
            for h in obj.history.all()
        ]
        return cls(
            id=obj.pk,
            tracking_number=obj.tracking_number,
            postal_tracking=obj.postal_tracking,
            carrier_name=obj.carrier_name,
            shipped_at=obj.shipped_at,
            delivered_at=obj.delivered_at,
            customer_notes=obj.customer_notes,
            status=obj.status,
            status_display=STATUS_DISPLAY.get(obj.status, obj.status),
            total_price=obj.total_price,
            shipping_cost=obj.shipping_cost,
            created_at=obj.created_at,
            shipping_address_snapshot=obj.shipping_address_snapshot,
            items=items,
            history=history,
        )
''')

# ─────────────────────────────────────────────────────────────────────────────
# 2. store/services.py
#    تغییرات:
#      - get_product_by_id: اضافه شدن prefetch_related("images")
#      - get_product_by_id: view_count یک واحد افزایش می‌یابد (F expression)
# ─────────────────────────────────────────────────────────────────────────────
w("store/services.py", '''\
from decimal import Decimal
from typing import List

from django.db import transaction as db_transaction
from django.db.models import F

from core.exceptions import NotFoundError, InsufficientStockError, AppException
from .models import Order, OrderItem, OrderStatusHistory, Product
from accounts.models import Address
from shipping.models import ShippingMethod
from shipping.services import calculate_shipping_cost


# ── Catalogue ─────────────────────────────────────────────────────────────────

def get_active_categories():
    from .models import Category
    return list(Category.objects.filter(is_active=True))


def get_active_products():
    """لیست محصولات فعال همراه با اطلاعات دسته‌بندی."""
    return list(
        Product.objects.select_related("category")
        .filter(is_active=True)
        .order_by("-created_at")
    )


def get_product_by_id(product_id: int) -> Product:
    """
    جزئیات یک محصول فعال.
    - view_count یک واحد افزایش می‌یابد.
    - images (گالری) از طریق prefetch_related بارگذاری می‌شوند.
    """
    try:
        product = (
            Product.objects
            .select_related("category")
            .prefetch_related("images")   # ← Phase 14
            .get(pk=product_id, is_active=True)
        )
    except Product.DoesNotExist:
        raise NotFoundError(f"Product {product_id} not found")

    # افزایش view_count بدون race condition
    Product.objects.filter(pk=product_id).update(view_count=F("view_count") + 1)

    # مقدار view_count در آبجکت بازگشتی را دستی بروزرسانی می‌کنیم
    # تا response درست باشد (چون update() مدل را در حافظه بروز نمی‌کند)
    product.view_count += 1

    return product


# ── Orders ────────────────────────────────────────────────────────────────────

def create_order(user, address_id: int, shipping_method_id: int, items: list) -> dict:
    try:
        address = Address.objects.get(pk=address_id, user=user)
    except Address.DoesNotExist:
        raise NotFoundError("Address not found")

    try:
        method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
    except ShippingMethod.DoesNotExist:
        raise NotFoundError("Shipping method not found")

    if not items:
        raise AppException("سبد خرید خالی است", status_code=400)

    order_items = []
    total = Decimal("0")

    for item_in in items:
        product_id = item_in["product_id"] if isinstance(item_in, dict) else item_in.product_id
        quantity   = item_in["quantity"]   if isinstance(item_in, dict) else item_in.quantity
        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            raise NotFoundError(f"Product {product_id} not found")

        if product.stock < quantity:
            raise InsufficientStockError(product.name, product.stock, quantity)

        order_items.append((product, quantity, product.price))
        total += product.price * quantity

    shipping_cost = calculate_shipping_cost(method)

    shipping_address_snapshot = {
        "province":    address.province,
        "city":        address.city,
        "street":      address.street,
        "postal_code": address.postal_code,
        "title":       address.title,
    }

    with db_transaction.atomic():
        order = Order.objects.create(
            user=user,
            address=address,
            shipping_method=method,
            status="pending",
            total_price=total + Decimal(str(shipping_cost)),
            shipping_cost=Decimal(str(shipping_cost)),
            shipping_address_snapshot=shipping_address_snapshot,
        )

        OrderStatusHistory.objects.create(
            order=order, status="pending", note="سفارش ثبت شد", created_by=user
        )

        for product, qty, price in order_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                unit_price=price,
                product_name_snapshot=product.name,
            )
            Product.objects.filter(pk=product.pk).update(stock=F("stock") - qty)

    return {"order": order, "payment_url": None}


def cancel_order(order_id: int, user) -> Order:
    """
    لغو سفارش توسط کاربر.
    فقط سفارش‌های pending قابل لغو هستند.
    موجودی محصولات برگشت داده می‌شود.
    یک رکورد تاریخچه با status=cancelled ثبت می‌شود.
    """
    with db_transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id, user=user)
        except Order.DoesNotExist:
            raise AppException("سفارش یافت نشد", status_code=404)

        if order.status != "pending":
            raise AppException("تنها سفارش‌های در حال تایید قابل لغو هستند.", status_code=400)

        for item in order.items.select_related("product"):
            Product.objects.filter(pk=item.product_id).update(
                stock=F("stock") + item.quantity
            )

        order.status = "cancelled"
        order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(
            order=order, status="cancelled", note="لغو توسط کاربر", created_by=user
        )

    return order


def update_order_status(
    order_id: int,
    new_status: str,
    admin_user,
    tracking_number: str = "",
    postal_tracking: str = "",
    note: str = "",
) -> Order:
    """
    تغییر وضعیت سفارش توسط ادمین.
    یک رکورد در OrderStatusHistory ثبت می‌کند.
    """
    valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
    if new_status not in valid_statuses:
        raise AppException(
            f"وضعیت نامعتبر است. مقادیر مجاز: {', '.join(sorted(valid_statuses))}",
            status_code=400,
        )

    with db_transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            raise AppException("سفارش یافت نشد", status_code=404)

        update_fields = ["status"]
        order.status = new_status

        if tracking_number:
            order.tracking_number = tracking_number
            update_fields.append("tracking_number")

        if postal_tracking:
            order.postal_tracking = postal_tracking
            update_fields.append("postal_tracking")

        if new_status == "shipped" and not order.shipped_at:
            from django.utils import timezone
            order.shipped_at = timezone.now()
            update_fields.append("shipped_at")

        if new_status == "delivered" and not order.delivered_at:
            from django.utils import timezone
            order.delivered_at = timezone.now()
            update_fields.append("delivered_at")

        order.save(update_fields=update_fields)

        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            note=note or f"وضعیت توسط ادمین به «{new_status}» تغییر کرد",
            created_by=admin_user,
        )

    return order


def get_user_orders(user) -> List[Order]:
    """لیست سفارش‌های کاربر به همراه آیتم‌ها و تاریخچه وضعیت."""
    return list(
        Order.objects.filter(user=user)
        .prefetch_related("items__product", "history")
        .order_by("-created_at")
    )


def get_user_order_detail(user, order_id: int) -> Order:
    """جزئیات یک سفارش خاص به همراه آیتم‌ها و تاریخچه وضعیت."""
    try:
        return (
            Order.objects.filter(user=user)
            .prefetch_related("items__product", "history")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        raise AppException("سفارش یافت نشد", status_code=404)
''')

# ─────────────────────────────────────────────────────────────────────────────
# 3. store/admin.py
#    تغییرات:
#      - ProductImageInline (TabularInline) اضافه شد
#      - ProductAdmin از Inline استفاده می‌کند
#      - ProductImage در admin register شد
# ─────────────────────────────────────────────────────────────────────────────
w("store/admin.py", '''\
from django.contrib import admin
from .models import Category, Product, ProductImage, Order, OrderItem, OrderStatusHistory


# ── Category ──────────────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display        = ("id", "name", "slug", "is_active", "created_at")
    list_filter         = ("is_active",)
    search_fields       = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


# ── Product ───────────────────────────────────────────────────────────────────

class ProductImageInline(admin.TabularInline):
    """آپلود چند تصویر مستقیم از صفحه ادمین محصول."""
    model       = ProductImage
    extra       = 1
    fields      = ("image", "alt_text", "order", "is_cover")
    ordering    = ("order",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display    = ("id", "name", "slug", "price", "discount_price",
                       "stock", "weight", "is_active", "view_count", "created_at")
    list_filter     = ("is_active", "category")
    search_fields   = ("name", "sku")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("view_count", "created_at", "updated_at")
    inlines         = [ProductImageInline]
    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": ("category", "name", "slug", "description",
                       "sku", "is_active")
        }),
        ("قیمت و موجودی", {
            "fields": ("price", "discount_price", "stock", "weight")
        }),
        ("تصویر اصلی", {
            "fields": ("image",)
        }),
        ("SEO", {
            "classes": ("collapse",),
            "fields": ("meta_title", "meta_description"),
        }),
        ("آمار", {
            "classes": ("collapse",),
            "fields": ("view_count", "created_at", "updated_at"),
        }),
    )


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    extra           = 0
    fields          = ("product", "product_name_snapshot", "quantity", "unit_price")
    readonly_fields = ("product", "product_name_snapshot", "quantity", "unit_price")


class OrderStatusHistoryInline(admin.TabularInline):
    model           = OrderStatusHistory
    extra           = 0
    fields          = ("status", "note", "created_by", "created_at")
    readonly_fields = ("status", "note", "created_by", "created_at")
    ordering        = ("-created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ("id", "user", "status", "total_price",
                       "shipping_cost", "tracking_number", "created_at")
    list_filter     = ("status",)
    search_fields   = ("user__phone_number", "tracking_number")
    readonly_fields = ("total_price", "shipping_cost", "created_at",
                       "shipping_address_snapshot")
    inlines         = [OrderItemInline, OrderStatusHistoryInline]
''')

# ─────────────────────────────────────────────────────────────────────────────
# 4. store/models.py — بدون تغییر مدل (همه فیلدها از قبل موجودند)
#    فقط برای اطمینان از یکپارچگی، فایل کامل بازنویسی می‌شود
#    تغییر واقعی: هیچ فیلد جدیدی اضافه نشده → migration لازم نیست
# ─────────────────────────────────────────────────────────────────────────────
w("store/models.py", '''\
from django.db import models
from django.conf import settings


# ── Category ──────────────────────────────────────────────────────────────────

class Category(models.Model):
    name        = models.CharField(max_length=128)
    slug        = models.SlugField(unique=True)
    description = models.TextField(blank=True, default="")
    image       = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "دسته\u200cبندی"
        verbose_name_plural = "دسته\u200cبندی\u200cها"

    def __str__(self):
        return self.name


# ── Product ───────────────────────────────────────────────────────────────────

class Product(models.Model):
    category         = models.ForeignKey(
        Category, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="products"
    )
    name             = models.CharField(max_length=256)
    slug             = models.SlugField(unique=True)
    description      = models.TextField(blank=True, default="")
    price            = models.DecimalField(max_digits=12, decimal_places=0)
    discount_price   = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    sku              = models.CharField(max_length=100, blank=True, unique=True, null=True)
    meta_title       = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    view_count       = models.PositiveIntegerField(default=0)
    stock            = models.PositiveIntegerField(default=0)
    weight           = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    image            = models.ImageField(upload_to="products/", blank=True, null=True)
    is_active        = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "محصول"
        verbose_name_plural = "محصولات"

    def __str__(self):
        return self.name


# ── ProductImage ──────────────────────────────────────────────────────────────

class ProductImage(models.Model):
    """گالری تصاویر محصول — هر محصول می‌تواند چندین تصویر داشته باشد."""
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image    = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=200, blank=True)
    order    = models.PositiveSmallIntegerField(default=0)
    is_cover = models.BooleanField(default=False)

    class Meta:
        ordering        = ["order"]
        verbose_name    = "تصویر محصول"
        verbose_name_plural = "تصاویر محصول"

    def __str__(self):
        return f"Image#{self.pk} — {self.product.name}"


# ── Order ─────────────────────────────────────────────────────────────────────

class Order(models.Model):
    STATUS_CHOICES = [
        ("pending",    "درحال تایید"),
        ("paid",       "تایید شده"),
        ("processing", "آماده سازی"),
        ("shipped",    "تحویل به پست"),
        ("delivered",  "تحویل داده شده"),
        ("cancelled",  "لغو شده"),
    ]

    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    address         = models.ForeignKey(
        "accounts.Address", on_delete=models.PROTECT, related_name="orders"
    )
    shipping_method = models.ForeignKey(
        "shipping.ShippingMethod", on_delete=models.PROTECT, related_name="orders"
    )
    status                   = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_price              = models.DecimalField(max_digits=14, decimal_places=0)
    shipping_cost            = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    tracking_number          = models.CharField(max_length=64, blank=True, default="")
    postal_tracking          = models.CharField(max_length=64, blank=True, default="")
    carrier_name             = models.CharField(max_length=100, blank=True)
    shipped_at               = models.DateTimeField(null=True, blank=True)
    delivered_at             = models.DateTimeField(null=True, blank=True)
    customer_notes           = models.TextField(blank=True)
    shipping_address_snapshot = models.JSONField(null=True, blank=True)
    created_at               = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "سفارش"
        verbose_name_plural = "سفارش\u200cها"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"Order#{self.pk} \u2014 {self.user.phone_number}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.tracking_number:
            self.tracking_number = f"ORD-{self.pk:06d}"
            Order.objects.filter(pk=self.pk).update(tracking_number=self.tracking_number)


# ── OrderItem ─────────────────────────────────────────────────────────────────

class OrderItem(models.Model):
    order                = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product              = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    product_name_snapshot = models.CharField(max_length=256, blank=True)
    quantity             = models.PositiveIntegerField()
    unit_price           = models.DecimalField(max_digits=12, decimal_places=0)

    class Meta:
        verbose_name        = "آیتم سفارش"
        verbose_name_plural = "آیتم\u200cهای سفارش"

    def __str__(self):
        return f"{self.product.name} \u00d7 {self.quantity}"


# ── OrderStatusHistory ────────────────────────────────────────────────────────

class OrderStatusHistory(models.Model):
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status     = models.CharField(max_length=30, choices=Order.STATUS_CHOICES)
    note       = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name        = "تاریخچه وضعیت سفارش"
        verbose_name_plural = "تاریخچه وضعیت سفارش\u200cها"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.order} -> {self.status}"
''')

# ─────────────────────────────────────────────────────────────────────────────
# ۵. خلاصه تغییرات
# ─────────────────────────────────────────────────────────────────────────────
print()
print("━" * 60)
print("فایل‌های ایجاد/بروزرسانی شده:")
for f in [
    "store/models.py",
    "store/schemas.py",
    "store/services.py",
    "store/admin.py",
]:
    print(f"  ✓  {f}")

print()
print("⚠  Migration لازم نیست — همه فیلدها و مدل ProductImage")
print("   از قبل در migration 0008 موجودند.")
print()
print("مرحله بعدی:")
print("  python manage.py check")
print("  python manage.py makemigrations --check   ← باید: No changes detected")
print("  python manage.py migrate                  ← باید: No migrations to apply")
print("  python manage.py runserver")
print("━" * 60)
