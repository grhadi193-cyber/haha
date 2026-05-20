from ninja import Router
from core.exceptions import NotFoundError

router = Router(tags=["core"])


@router.get("/health", summary="Health check")
def health(request):
    """Returns 200 OK — used by load-balancers and CI."""
    return {"status": "ok"}


@router.get("/error-test", summary="Exception handler smoke-test")
def error_test(request):
    """
    Raises NotFoundError so you can verify the global handler
    returns structured JSON instead of an HTML 500.
    Remove or guard this endpoint before going to production.
    """
    raise NotFoundError("This is a test error from the global handler.")

from pydantic import BaseModel
from typing import Optional

class SiteSettingsOut(BaseModel):
    hero_title: str
    hero_text: str
    hero_banner: Optional[str] = None
    about_us: str

@router.get("/settings", response=SiteSettingsOut, summary="Get site settings")
def get_site_settings(request):
    from core.models import SiteSettings
    settings = SiteSettings.objects.first()
    if not settings:
        settings = SiteSettings.objects.create()
    
    banner_url = request.build_absolute_uri(settings.hero_banner.url) if settings.hero_banner else None
    return SiteSettingsOut(
        hero_title=settings.hero_title,
        hero_text=settings.hero_text,
        hero_banner=banner_url,
        about_us=settings.about_us
    )
