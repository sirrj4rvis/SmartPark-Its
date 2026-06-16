"""
payment_service.py — payments with a provider abstraction.

- RazorpayProvider is used when RAZORPAY_KEY_ID/SECRET are configured.
- MockProvider is the default (no keys) so the flow is fully demoable + testable
  locally without external dependencies.

Webhook handling is provider-agnostic and enforces two production concerns:
  * signature verification (HMAC-SHA256 over the raw body, constant-time compare)
  * idempotency (each provider event id is recorded and processed at most once)
"""
import base64
import hashlib
import hmac
import io
import secrets
from urllib.parse import quote

from flask import current_app

from ..extensions import db
from ..models import Booking, Payment, PaymentStatus, WebhookEvent


class PaymentError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
class MockProvider:
    name = "mock"

    def create_order(self, amount, currency, receipt):
        return {"id": f"order_mock_{secrets.token_hex(8)}", "amount": int(amount * 100),
                "currency": currency}

    @property
    def public_key(self):
        return "rzp_test_mock"


class RazorpayProvider:
    name = "razorpay"

    def __init__(self, key_id, key_secret):
        self.key_id = key_id
        self.key_secret = key_secret

    def create_order(self, amount, currency, receipt):
        import razorpay  # lazy: only needed when real keys are set

        client = razorpay.Client(auth=(self.key_id, self.key_secret))
        return client.order.create(
            {"amount": int(amount * 100), "currency": currency, "receipt": receipt,
             "payment_capture": 1}
        )

    @property
    def public_key(self):
        return self.key_id


def get_provider():
    key_id = current_app.config.get("RAZORPAY_KEY_ID")
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET")
    if key_id and key_secret:
        return RazorpayProvider(key_id, key_secret)
    return MockProvider()


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #
def create_payment_for_booking(booking: Booking) -> Payment:
    """Create (or return existing) a payment order for a completed booking."""
    if booking.total_cost is None or booking.total_cost <= 0:
        raise PaymentError("Booking has no payable amount.")
    existing = db.session.query(Payment).filter_by(booking_id=booking.id).first()
    if existing:
        return existing

    provider = get_provider()
    order = provider.create_order(booking.total_cost, current_app.config.get("CURRENCY_CODE", "INR"),
                                  receipt=f"booking_{booking.id}")
    payment = Payment(
        booking_id=booking.id, provider=provider.name, order_id=order["id"],
        amount=booking.total_cost, currency="INR", status=PaymentStatus.created,
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def upi_enabled() -> bool:
    from . import settings_service

    return bool(settings_service.get("upi_vpa"))


def upi_payment_uri(payment: Payment) -> str:
    """Build a standard UPI deep link. Scanning it in any UPI app pre-fills the
    payee VPA and the exact amount (NPCI UPI URI spec)."""
    from . import settings_service

    vpa = settings_service.get("upi_vpa")
    name = settings_service.get("upi_payee_name")
    note = f"SmartPark booking #{payment.booking_id}"
    return (
        f"upi://pay?pa={quote(vpa)}&pn={quote(name)}"
        f"&am={payment.amount:.2f}&cu=INR&tn={quote(note)}&tr={quote(payment.order_id)}"
    )


def upi_qr_data_uri(payment: Payment) -> str:
    """Render the UPI payment link as a scannable QR (base64 PNG data-URI)."""
    try:
        import qrcode
    except Exception:  # pragma: no cover
        return ""
    img = qrcode.make(upi_payment_uri(payment))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def mark_paid(order_id: str, payment_ref: str = None) -> Payment:
    payment = db.session.query(Payment).filter_by(order_id=order_id).first()
    if not payment:
        raise PaymentError("Unknown order.")
    if payment.status != PaymentStatus.paid:
        payment.status = PaymentStatus.paid
        payment.payment_ref = payment_ref
        db.session.commit()
    return payment


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Razorpay signs the raw request body with HMAC-SHA256 using the webhook secret."""
    secret = current_app.config["RAZORPAY_WEBHOOK_SECRET"].encode()
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)


def sign_payload(raw_body: bytes) -> str:
    """Helper (used by tests / mock confirm) to produce a valid signature."""
    secret = current_app.config["RAZORPAY_WEBHOOK_SECRET"].encode()
    return hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


def handle_webhook_event(event: dict) -> str:
    """Idempotently process a webhook event. Returns a short status string."""
    event_id = event.get("id") or event.get("event_id")
    if not event_id:
        raise PaymentError("Missing event id.")

    # Idempotency: record-or-skip.
    if db.session.get(WebhookEvent, event_id):
        return "duplicate"
    db.session.add(WebhookEvent(event_id=event_id, provider="razorpay"))

    etype = event.get("event", "")
    order_id, payment_ref = _extract_order(event)
    if etype in ("payment.captured", "order.paid") and order_id:
        payment = db.session.query(Payment).filter_by(order_id=order_id).first()
        if payment and payment.status != PaymentStatus.paid:
            payment.status = PaymentStatus.paid
            payment.payment_ref = payment_ref
    db.session.commit()
    return "processed"


def _extract_order(event: dict):
    try:
        entity = event["payload"]["payment"]["entity"]
        return entity.get("order_id"), entity.get("id")
    except (KeyError, TypeError):
        try:
            entity = event["payload"]["order"]["entity"]
            return entity.get("id"), None
        except (KeyError, TypeError):
            return None, None
