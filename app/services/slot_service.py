"""
slot_service.py — slot queries and admin CRUD.

Availability listing is cached in Redis (short TTL) and invalidated on any
mutation, so the hot dashboard read does not hammer the DB.
"""
from sqlalchemy.exc import IntegrityError

from ..extensions import cache, db
from ..models import Booking, BookingStatus, ParkingSlot, SlotStatus, VehicleType

_AVAIL_KEY = "slots:availability"


class SlotError(Exception):
    pass


def invalidate_availability():
    cache.delete(_AVAIL_KEY)


def list_slots():
    return db.session.query(ParkingSlot).order_by(ParkingSlot.slot_number).all()


def availability_snapshot():
    """Cached lightweight list used by the live grid / API."""
    cached = cache.get(_AVAIL_KEY)
    if cached is not None:
        return cached
    data = [s.to_dict() for s in list_slots()]
    cache.set(_AVAIL_KEY, data, timeout=15)
    return data


def counts():
    total = db.session.query(ParkingSlot).count()
    available = db.session.query(ParkingSlot).filter_by(status=SlotStatus.available).count()
    occupied = db.session.query(ParkingSlot).filter_by(status=SlotStatus.occupied).count()
    reserved = db.session.query(ParkingSlot).filter_by(status=SlotStatus.reserved).count()
    return {"total": total, "available": available, "occupied": occupied, "reserved": reserved}


def add_slot(slot_number: str, location: str, vehicle_type: str, base_rate: float):
    slot_number = (slot_number or "").strip().upper()
    location = (location or "").strip().title()
    if not slot_number or not location:
        raise SlotError("Slot number and location are required.")
    try:
        vt = VehicleType(vehicle_type)
    except ValueError:
        raise SlotError("Invalid vehicle type.")
    if base_rate is None or base_rate <= 0:
        raise SlotError("Rate must be a positive number.")

    slot = ParkingSlot(
        slot_number=slot_number, location=location, vehicle_type=vt, base_rate=float(base_rate)
    )
    db.session.add(slot)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise SlotError(f"Slot {slot_number} already exists.")
    invalidate_availability()
    return slot


def delete_slot(slot_id: int):
    slot = db.session.get(ParkingSlot, slot_id)
    if not slot:
        raise SlotError("Slot not found.")
    if slot.status == SlotStatus.occupied:
        raise SlotError("Cannot delete an occupied slot.")
    if slot.bookings.count() > 0:
        raise SlotError("Cannot delete a slot with booking history. Disable it instead.")
    db.session.delete(slot)
    db.session.commit()
    invalidate_availability()


def toggle_slot(slot_id: int):
    slot = db.session.get(ParkingSlot, slot_id)
    if not slot:
        raise SlotError("Slot not found.")
    if slot.status == SlotStatus.occupied:
        # Force-free: also complete any active booking on it.
        active = (
            db.session.query(Booking)
            .filter_by(slot_id=slot.id, status=BookingStatus.active)
            .first()
        )
        if active:
            active.status = BookingStatus.cancelled
        slot.status = SlotStatus.available
    else:
        slot.status = SlotStatus.occupied
    slot.reserved_until = None
    db.session.commit()
    invalidate_availability()
    return slot
