from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from ninja import NinjaAPI

from core.api import router as core_router
from accounts.api import router as accounts_router
from store.api import router as store_router
from shipping.api import router as shipping_router

api = NinjaAPI(
    title="Shop API",
    version="1.0.0",
    docs_url="/api/docs",
)

api.add_router("/", core_router)
api.add_router("/auth", accounts_router)
api.add_router("/", store_router)
api.add_router("/shipping", shipping_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", api.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    try:
        import debug_toolbar
        urlpatterns = [
            path("__debug__/", include("debug_toolbar.urls")),
        ] + urlpatterns
    except ImportError:
        pass
