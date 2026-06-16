"""
notification_service.py — receipts (QR) and user notifications.

QR encodes a verifiable receipt payload. Notification delivery is abstracted
behind a provider interface; the default logs (and, if configured, hands off to
a Celery task for async email/SMS) so the call sites stay clean.
"""
import base64
import io

from flask import current_app


def receipt_qr_data_uri(booking) -> str:
    """Return a base64 PNG data-URI QR encoding the receipt summary."""
    try:
        import qrcode
    except Exception:  # pragma: no cover - optional dep
        return ""
    payload = (
        f"SMARTPARK|receipt={booking.id}|slot={booking.slot.slot_number}"
        f"|vehicle={booking.vehicle_number}|amount={current_app.config['CURRENCY']}{booking.total_cost}"
    )
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def notify(user_email: str, subject: str, body: str):
    """Send a notification. Async via Celery when a broker is configured."""
    logger = current_app.logger
    try:
        from ..tasks import send_notification

        if current_app.config.get("CELERY_BROKER_URL", "memory://") != "memory://":
            send_notification.delay(user_email, subject, body)
            return
    except Exception:
        pass
    logger.info("notification", extra={"to": user_email, "subject": subject})
