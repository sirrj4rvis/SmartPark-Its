"""Service-layer unit tests: slots, forecasting, notifications, tasks."""
from app.models import Booking, BookingStatus, ParkingSlot, SlotStatus
from app.services import (
    booking_service,
    forecast_service,
    notification_service,
    slot_service,
)


# ---------------- slot_service ----------------
def test_counts_and_availability_snapshot(app):
    c = slot_service.counts()
    assert c["total"] == 15 and c["available"] == 15
    snap = slot_service.availability_snapshot()
    assert len(snap) == 15 and "current_rate" in snap[0]


def test_add_slot_validation(app, db):
    slot = slot_service.add_slot("Z1", "Test Block", "car", 25.0)
    assert slot.slot_number == "Z1"
    # duplicate
    import pytest
    with pytest.raises(slot_service.SlotError):
        slot_service.add_slot("Z1", "Test Block", "car", 25.0)
    # bad vehicle type
    with pytest.raises(slot_service.SlotError):
        slot_service.add_slot("Z2", "Test", "spaceship", 25.0)
    # bad rate
    with pytest.raises(slot_service.SlotError):
        slot_service.add_slot("Z3", "Test", "car", -5)


def test_delete_slot_rules(app, db, first_slot, make_user):
    # occupied slot can't be deleted
    user = make_user()
    booking_service.book_slot(user.id, first_slot.id, "KA01AB1234")
    import pytest
    with pytest.raises(slot_service.SlotError):
        slot_service.delete_slot(first_slot.id)
    # slot with history can't be deleted
    booking_service.exit_booking(user.id, db.session.query(Booking).first().id)
    with pytest.raises(slot_service.SlotError):
        slot_service.delete_slot(first_slot.id)


def test_toggle_slot_frees_active_booking(app, db, first_slot, make_user):
    user = make_user()
    booking_service.book_slot(user.id, first_slot.id, "KA01AB1234")
    slot_service.toggle_slot(first_slot.id)  # occupied -> available, cancels booking
    assert db.session.get(ParkingSlot, first_slot.id).status == SlotStatus.available
    assert db.session.query(Booking).first().status == BookingStatus.cancelled


# ---------------- forecast_service ----------------
def test_forecast_empty_history(app):
    p = forecast_service.predict_occupancy()
    assert 0.0 <= p["predicted_ratio"] <= 1.0
    assert p["confidence"] == "low"


def test_forecast_with_history(app, db, first_slot, make_user):
    user = make_user()
    b = booking_service.book_slot(user.id, first_slot.id, "KA01AB1234")
    booking_service.exit_booking(user.id, b.id)
    profile = forecast_service.build_demand_profile()
    assert isinstance(profile, dict)
    fc = forecast_service.next_24h_forecast()
    assert len(fc["labels"]) == 24 and len(fc["values"]) == 24


def test_recommend_slots(app):
    recs = forecast_service.recommend_slots(limit=3)
    assert len(recs) == 3
    # cheapest first
    rates = [r["current_rate"] for r in recs]
    assert rates == sorted(rates)
    bikes = forecast_service.recommend_slots(vehicle_type="bike")
    assert all(s["vehicle_type"] == "bike" for s in bikes)


# ---------------- notification_service ----------------
def test_receipt_qr_data_uri(app, db, first_slot, make_user):
    user = make_user()
    b = booking_service.book_slot(user.id, first_slot.id, "KA01AB1234")
    booking_service.exit_booking(user.id, b.id)
    booking = db.session.query(Booking).first()
    uri = notification_service.receipt_qr_data_uri(booking)
    assert uri.startswith("data:image/png;base64,")


def test_notify_logs(app, caplog):
    notification_service.notify("x@test.com", "Hello", "Body")  # should not raise


# ---------------- tasks (called directly) ----------------
def test_tasks_run_in_app_context(app, db, first_slot, make_user):
    from app import tasks
    from datetime import timedelta
    from app.models import utcnow

    user = make_user()
    booking_service.reserve_slot(user.id, first_slot.id)
    slot = db.session.get(ParkingSlot, first_slot.id)
    slot.reserved_until = utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert tasks.sweep_reservations() == 1
    assert tasks.reprice() >= 1.0
    assert tasks.send_notification("a@b.com", "s", "b") is True
