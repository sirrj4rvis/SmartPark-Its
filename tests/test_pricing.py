"""Dynamic pricing engine."""
from app.services import pricing_service


def test_no_surge_below_threshold(app):
    assert pricing_service.compute_surge(0.0) == 1.0
    assert pricing_service.compute_surge(app.config["PRICING_SURGE_THRESHOLD"]) == 1.0


def test_surge_ramps_to_cap_at_full_occupancy(app):
    cap = app.config["PRICING_SURGE_MAX"]
    assert pricing_service.compute_surge(1.0) == cap


def test_surge_is_monotonic(app):
    a = pricing_service.compute_surge(0.7)
    b = pricing_service.compute_surge(0.9)
    assert b >= a >= 1.0


def test_reprice_updates_slot_rates(app, make_user, first_slot, db):
    from app.services import booking_service

    base = first_slot.base_rate
    user = make_user()
    # Book several slots to push occupancy up, triggering surge.
    from app.models import ParkingSlot

    slots = db.session.query(ParkingSlot).all()
    # Occupy ~80% of slots directly.
    from app.models import SlotStatus

    for s in slots[: int(len(slots) * 0.8)]:
        s.status = SlotStatus.occupied
    db.session.commit()
    multiplier = pricing_service.reprice_all()
    assert multiplier > 1.0
    refreshed = db.session.get(ParkingSlot, first_slot.id)
    assert refreshed.current_rate >= base
