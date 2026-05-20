# PHASE 14 — Multi-Image Products

## Goal
Allow each product to have multiple images (gallery) in addition to the existing primary image.

## Context
- store.Product currently has: image = ImageField(upload_to="products/", blank=True, null=True)
  → Keep this field as-is (primary/legacy, do NOT remove)
- store/schemas.py: ProductDetailOut extends ProductListOut
- store/admin.py: ProductAdmin exists (needs inline added)

## Deliverables

### store/models.py (update)
Add ProductImage model (after Product class):
```python
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image   = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=255, blank=True, default="")
    order   = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصول"

    def __str__(self):
        return f"{self.product.name} — image #{self.order}"
```

### store/schemas.py (update)
Add:
```python
class ProductImageOut(BaseModel):
    id:       int
    image:    str          # full URL resolved by service layer
    alt_text: str
    order:    int

    class Config:
        from_attributes = True
```

Update ProductDetailOut — add field:
```python
images: List[ProductImageOut] = []
```

### store/services.py (update)
Update get_product_by_id to prefetch gallery images:
```python
Product.objects.prefetch_related("images").get(pk=product_id, is_active=True)
```

In the API layer (store/api.py), when building ProductDetailOut, resolve image URLs:
- For each img in product.images.all():
  image_url = request.build_absolute_uri(img.image.url) if img.image else ""

### store/api.py (update)
Update GET /api/products/{product_id} endpoint:
- After fetching product, build images list with absolute URLs
- Pass as `images=[...]` to ProductDetailOut constructor

### store/admin.py (update)
Add inline and update ProductAdmin:
```python
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "order")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    list_display = ("name", "price", "stock", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
```

### Migration Required
- store/migrations/000X_productimage.py
  (check existing store migrations to determine correct number)
  Dependencies must include the latest existing store migration.

## Target Files
- store/models.py
- store/schemas.py
- store/services.py
- store/api.py
- store/admin.py
- store/migrations/000X_productimage.py

## Acceptance Criteria
- makemigrations + migrate OK
- GET /api/products/1 → 200, includes "images": [] (empty list if no gallery images)
- After adding images via /admin, GET /api/products/1 → images list with full URLs
- GET /api/products still works unchanged (list endpoint has NO images field — only detail)
- Admin: Product edit page shows tabular inline for gallery images
- Swagger: ProductDetailOut schema shows images field as array
