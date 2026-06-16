"""
booking_service.py — race-safe booking lifecycle.

Concurrency strategy (defence in depth):
  1. SELECT ... FOR UPDATE locks the slot row (Postgres) so concurrent bookers
     serialize on it.
  2. The partial unique index uq_active_booking_per_slot is the hard guarantee:
     even if locking is unavailable (e.g. SQLite), the DB rejects a second
     active booking with an IntegrityError, which we translate to a clean error.
  3. Reservations carry a TTL; expired ones are swept by a Celery beat task and
     also opportunistically here.
"""
import math
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Booking, BookingStatus, ParkingSlot, SlotStatus, as_utc, utcnow
from . import pricing_service, slot_service


class BookingError(Exception):
    """Domain error with a user-safe message."""


def _lock_slot(slot_id: int) -> ParkingSlot:
    q = db.session.query(ParkingSlot).filter(ParkingSlot.id == slot_id)
    # with_for_update is a no-op on SQLite but real on Postgres.
    if db.session.bind and db.session.bind.dialect.name == "postgresql":
        q = q.with_for_update()
    slot = q.first()
    if not slot:
        raise BookingError("Slot not found.")
    return slot


def _release_if_reservation_expired(slot: ParkingSlot):
    if (
        slot.status == SlotStatus.reserved
        and slot.reserved_until is not None
        and as_utc(slot.reserved_until) < utcnow()
    ):
        slot.status = SlotStatus.available
        slot.reserved_until = None


def reserve_slot(user_id: int, slot_id: int) -> ParkingSlot:
    """Hold a slot for the configured TTL before the user confirms."""
    slot = _lock_slot(slot_id)
    _release_if_reservation_expired(slot)
    if slot.status != SlotStatus.available:
        raise BookingError(f"Slot {slot.slot_number} is not available.")
    from . import settings_service

    ttl = settings_service.get("reservation_ttl_minutes")
    slot.status = SlotStatus.reserved
    slot.reserved_until = utcnow() + timedelta(minutes=ttl)
    db.session.commit()
    slot_service.invalidate_availability()
    return slot


def book_slot(user_id: int, slot_id: int, vehicle_number: str) -> Booking:
    """Create an active booking, marking the slot occupied. Race-safe."""
    vehicle_number = (vehicle_number or "").strip().upper()
    if not vehicle_number:
        raise BookingError("Vehicle number is required.")

    # Reject if the user already holds an active booking.
    existing = (
        db.session.query(Booking)
        .filter_by(user_id=user_id, status=BookingStatus.active)
        .first()
    )
    if existing:
        raise BookingError("You already have an active booking. Exit it first.")

    slot = _lock_slot(slot_id)
    _release_if_reservation_expired(slot)
    if slot.status == SlotStatus.occupied:
        raise BookingError(f"Slot {slot.slot_number} is already occupied.")

    booking = Booking(
        user_id=user_id,
        slot_id=slot.id,
        vehicle_number=vehicle_number,
        rate_applied=slot.current_rate,
        status=BookingStatus.active,
    )
    slot.status = SlotStatus.occupied
    slot.reserved_until = None
    db.session.add(booking)
    try:
        db.session.commit()
    except IntegrityError:
        # The unique index fired — someone beat us to it.
        db.session.rollback()
        raise BookingError("That slot was just taken. Please pick another.")

    pricing_service.reprice_all()
    slot_service.invalidate_availability()
    return booking


def exit_booking(user_id: int, booking_id: int) -> Booking:
    """Close a booking, compute the final cost, free the slot."""
    booking = (
        db.session.query(Booking)
        .filter_by(id=booking_id, user_id=user_id, status=BookingStatus.active)
        .first()
    )
    if not booking:
        raise BookingError("Active booking not found.")

    slot = _lock_slot(booking.slot_id)
    end = utcnow()
    duration_minutes = max(1, int((end - as_utc(booking.start_time)).total_seconds() // 60))
    min_hours = current_app.config["MIN_BILLED_HOURS"]
    hours_billed = max(math.ceil(duration_minutes / 60), min_hours)
    rate = booking.rate_applied or slot.current_rate

    booking.end_time = end
    booking.duration_minutes = duration_minutes
    booking.total_cost = round(hours_billed * rate, 2)
    booking.status = BookingStatus.completed
    slot.status = SlotStatus.available
    slot.reserved_until = None
    db.session.commit()

    pricing_service.reprice_all()
    slot_service.invalidate_availability()
    return booking


def sweep_expired_reservations() -> int:
    """Free any reservations whose TTL has lapsed. Returns count released."""
    now = utcnow()
    expired = (
        db.session.query(ParkingSlot)
        .filter(ParkingSlot.status == SlotStatus.reserved, ParkingSlot.reserved_until < now)
        .all()
    )
    for slot in expired:
        slot.status = SlotStatus.available
        slot.reserved_until = None
    if expired:
        db.session.commit()
        slot_service.invalidate_availability()
    return len(expired)
