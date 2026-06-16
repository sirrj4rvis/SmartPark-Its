"""Booking lifecycle + the concurrency guarantee."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Booking, BookingStatus, ParkingSlot, SlotStatus
from app.services import booking_service


def test_book_marks_slot_occupied(app, make_user, first_slot, db):
    user = make_user()
    booking = booking_service.book_slot(user.id, first_slot.id, "KA01AB1234")
    assert booking.status == BookingStatus.active
    assert db.session.get(ParkingSlot, first_slot.id).status == SlotStatus.occupied


def test_cannot_double_book_same_slot(app, make_user, first_slot):
    u1 = make_user(email="a@test.com")
    u2 = make_user(email="b@test.com")
    booking_service.book_slot(u1.id, first_slot.id, "KA01AB1111")
    with pytest.raises(booking_service.BookingError):
        booking_service.book_slot(u2.id, first_slot.id, "KA01AB2222")


def test_db_constraint_blocks_two_active_bookings(app, make_user, first_slot, db):
    """The partial unique index is the hard guarantee — bypass the service
    layer and prove the DATABASE rejects a second active booking."""
    u1 = make_user(email="x@test.com")
    u2 = make_user(email="y@test.com")
    db.session.add(Booking(user_id=u1.id, slot_id=first_slot.id,
                           vehicle_number="A1", status=BookingStatus.active))
    db.session.commit()
    db.session.add(Booking(user_id=u2.id, slot_id=first_slot.id,
                           vehicle_number="A2", status=BookingStatus.active))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_cannot_hold_two_active_bookings(app, make_user, db):
    slots = db.session.query(ParkingSlot).limit(2).all()
    user = make_user()
    booking_service.book_slot(user.id, slots[0].id, "KA01AB1234")
    with pytest.raises(booking_service.BookingError):
        booking_service.book_slot(user.id, slots[1].id, "KA01AB5678")


def test_exit_computes_cost_and_frees_slot(app, make_user, first_slot, db):
    user = make_user()
    booking = booking_service.book_slot(user.id, first_slot.id, "KA01AB1234")
    closed = booking_service.exit_booking(user.id, booking.id)
    assert closed.status == BookingStatus.completed
    assert closed.total_cost is not None and closed.total_cost > 0
    assert db.session.get(ParkingSlot, first_slot.id).status == SlotStatus.available


def test_reservation_holds_then_expires(app, make_user, first_slot, db):
    from datetime import timedelta
    from app.models import utcnow

    user = make_user()
    booking_service.reserve_slot(user.id, first_slot.id)
    assert db.session.get(ParkingSlot, first_slot.id).status == SlotStatus.reserved
    # Force expiry and sweep.
    slot = db.session.get(ParkingSlot, first_slot.id)
    slot.reserved_until = utcnow() - timedelta(minutes=1)
    db.session.commit()
    released = booking_service.sweep_expired_reservations()
    assert released == 1
    assert db.session.get(ParkingSlot, first_slot.id).status == SlotStatus.available
