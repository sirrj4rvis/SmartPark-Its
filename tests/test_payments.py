"""Payments: order creation, webhook signature verification, idempotency, flow."""
import json

from app.models import Booking, Payment, PaymentStatus, WebhookEvent
from app.services import booking_service, payment_service


def _completed_booking(app, db, first_slot, make_user):
    user = make_user()
    b = booking_service.book_slot(user.id, first_slot.id, "KA01AB1234")
    return booking_service.exit_booking(user.id, b.id), user


def test_payment_created_on_exit_via_web(auth_client, first_slot, db):
    auth_client.post(f"/book/{first_slot.id}", data={"vehicle_number": "KA01AB1234"},
                     follow_redirects=True)
    booking = db.session.query(Booking).first()
    auth_client.post(f"/exit/{booking.id}", follow_redirects=True)
    payment = db.session.query(Payment).filter_by(booking_id=booking.id).first()
    assert payment is not None
    assert payment.status == PaymentStatus.created
    assert payment.amount == booking.total_cost


def test_create_payment_is_idempotent(app, db, first_slot, make_user):
    booking, _ = _completed_booking(app, db, first_slot, make_user)
    p1 = payment_service.create_payment_for_booking(booking)
    p2 = payment_service.create_payment_for_booking(booking)
    assert p1.id == p2.id  # no duplicate order


def test_mock_confirm_marks_paid(auth_client, first_slot, db):
    auth_client.post(f"/book/{first_slot.id}", data={"vehicle_number": "KA01AB1234"},
                     follow_redirects=True)
    booking = db.session.query(Booking).first()
    auth_client.post(f"/exit/{booking.id}", follow_redirects=True)
    payment = db.session.query(Payment).filter_by(booking_id=booking.id).first()
    r = auth_client.post(f"/payments/{payment.order_id}/mock-confirm", follow_redirects=True)
    assert r.status_code == 200
    db.session.expire_all()
    assert db.session.query(Payment).get(payment.id).status == PaymentStatus.paid


def test_webhook_rejects_bad_signature(client):
    body = json.dumps({"id": "evt_1", "event": "payment.captured"}).encode()
    r = client.post("/api/webhooks/razorpay", data=body,
                    headers={"X-Razorpay-Signature": "deadbeef", "Content-Type": "application/json"})
    assert r.status_code == 400


def test_webhook_accepts_valid_signature_and_marks_paid(app, client, db, first_slot, make_user):
    booking, _ = _completed_booking(app, db, first_slot, make_user)
    payment = payment_service.create_payment_for_booking(booking)

    event = {
        "id": "evt_unique_123", "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_abc", "order_id": payment.order_id}}},
    }
    body = json.dumps(event).encode()
    with app.test_request_context():
        sig = payment_service.sign_payload(body)

    r = client.post("/api/webhooks/razorpay", data=body,
                    headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})
    assert r.status_code == 200 and r.get_json()["status"] == "processed"
    db.session.expire_all()
    assert db.session.query(Payment).get(payment.id).status == PaymentStatus.paid


def test_upi_payment_uri_and_qr(app, db, first_slot, make_user):
    booking, _ = _completed_booking(app, db, first_slot, make_user)
    payment = payment_service.create_payment_for_booking(booking)
    app.config["UPI_VPA"] = "test@okhdfcbank"
    app.config["UPI_PAYEE_NAME"] = "SmartPark"
    uri = payment_service.upi_payment_uri(payment)
    assert uri.startswith("upi://pay?")
    assert "pa=test%40okhdfcbank" in uri  # VPA url-encoded
    assert f"am={payment.amount:.2f}" in uri and "cu=INR" in uri
    assert payment_service.upi_qr_data_uri(payment).startswith("data:image/png;base64,")
    assert payment_service.upi_enabled() is True


def test_upi_disabled_without_vpa(app):
    app.config["UPI_VPA"] = ""
    assert payment_service.upi_enabled() is False


def test_webhook_idempotent(app, client, db, first_slot, make_user):
    booking, _ = _completed_booking(app, db, first_slot, make_user)
    payment = payment_service.create_payment_for_booking(booking)
    event = {"id": "evt_dup_1", "event": "payment.captured",
             "payload": {"payment": {"entity": {"id": "pay_x", "order_id": payment.order_id}}}}
    body = json.dumps(event).encode()
    with app.test_request_context():
        sig = payment_service.sign_payload(body)
    h = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}

    first = client.post("/api/webhooks/razorpay", data=body, headers=h)
    second = client.post("/api/webhooks/razorpay", data=body, headers=h)
    assert first.get_json()["status"] == "processed"
    assert second.get_json()["status"] == "duplicate"
    assert db.session.query(WebhookEvent).count() == 1
