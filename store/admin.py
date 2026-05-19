from django.contrib import admin
from .models import Category, Product, Order, OrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ("id", "name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ("id", "name", "slug", "price", "stock", "is_active")
    list_filter   = ("is_active", "category")
    search_fields = ("name",)


class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    fields = ("product", "quantity", "unit_price")
    readonly_fields = ("product", "quantity", "unit_price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ("id", "user", "status", "total_price", "created_at")
    list_filter     = ("status",)
    search_fields   = ("user__phone_number",)
    readonly_fields = ("total_price", "shipping_cost", "created_at")
    inlines         = [OrderItemInline]
