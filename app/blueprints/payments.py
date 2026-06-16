"""
payments.py — payment confirmation (web) + provider webhook (machine).

- payments_bp: user-facing actions (CSRF-protected). The mock "pay now" button
  exists only when no real Razorpay keys are configured, so the demo works locally.
- pay_webhook_bp: the provider→server webhook. CSRF-exempt (no browser session);
  authenticated instead by HMAC signature verification + idempotency.
"""
from flask import Blueprint, abort, flash, redirect, request, url_for

from ..extensions import csrf
from ..models import Payment
from ..security import current_user, login_required
from ..services import payment_service

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")
pay_webhook_bp = Blueprint("pay_webhook", __name__)
csrf.exempt(pay_webhook_bp)


@payments_bp.post("/<order_id>/mock-confirm")
@login_required
def mock_confirm(order_id):
    """Demo-only: simulate a successful gateway payment (mock provider)."""
    if payment_service.get_provider().name != "mock":
        abort(404)
    from ..extensions import db

    payment = db.session.query(Payment).filter_by(order_id=order_id).first_or_404()
    # Authorize: the payment must belong to the current user's booking.
    if payment.booking.user_id != current_user().id:
        abort(403)
    payment_service.mark_paid(order_id, payment_ref="pay_mock_demo")
    flash("Payment successful! 🎉", "success")
    return redirect(url_for("user.receipt", booking_id=payment.booking_id))


@pay_webhook_bp.post("/api/webhooks/razorpay")
def razorpay_webhook():
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not payment_service.verify_webhook_signature(request.get_data(), signature):
        return {"error": "invalid signature"}, 400
    event = request.get_json(silent=True) or {}
    try:
        status = payment_service.handle_webhook_event(event)
    except payment_service.PaymentError as exc:
        return {"error": str(exc)}, 400
    return {"status": status}, 200
