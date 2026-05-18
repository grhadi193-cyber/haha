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
