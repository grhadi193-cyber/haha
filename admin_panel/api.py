from typing import List
from ninja import Router
from ninja.security import HttpBearer
from django.http import JsonResponse
from accounts.models import User
from store.models import Order
from pydantic import BaseModel
from store.schemas import UserOrderOut

router = Router(tags=["Admin"])

class AdminBearer(HttpBearer):
    def authenticate(self, request, token):
        from rest_framework_simplejwt.tokens import AccessToken
        from core.exceptions import AppException
        try:
            acc = AccessToken(token)
            user = User.objects.get(pk=acc["user_id"])
            if not user.is_staff:
                return None
            return user
        except Exception:
            return None

_auth = AdminBearer()

class DashboardOut(BaseModel):
    total_users: int
    total_orders: int
    total_revenue: int

@router.get("/dashboard", auth=_auth, response=DashboardOut, summary="داشبورد ادمین")
def admin_dashboard(request):
    total_users = User.objects.count()
    total_orders = Order.objects.count()
    total_revenue = sum(o.total_price for o in Order.objects.filter(status="paid"))
    return DashboardOut(
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue
    )

@router.get("/orders", auth=_auth, response=List[UserOrderOut], summary="سفارش‌های ادمین")
def admin_orders(request):
    return [UserOrderOut.model_validate(o) for o in Order.objects.all().order_by("-created_at")]

class UpdateOrderStatusIn(BaseModel):
    status: str
    tracking_number: str = ""
    postal_tracking: str = ""

@router.put("/orders/{order_id}/status", auth=_auth, summary="تغییر وضعیت سفارش")
def update_order_status(request, order_id: int, payload: UpdateOrderStatusIn):
    try:
        order = Order.objects.get(pk=order_id)
        order.status = payload.status
        if payload.tracking_number:
            order.tracking_number = payload.tracking_number
        if payload.postal_tracking:
            order.postal_tracking = payload.postal_tracking
        order.save(update_fields=["status", "tracking_number", "postal_tracking"])
        return {"detail": "وضعیت سفارش با موفقیت تغییر کرد"}
    except Order.DoesNotExist:
        return JsonResponse({"detail": "سفارش یافت نشد"}, status=404)
