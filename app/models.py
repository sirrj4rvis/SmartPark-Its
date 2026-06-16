"""
models.py — SQLAlchemy ORM models for SmartPark ITS.

Design notes:
- Status fields use Python enums for type-safety.
- A *partial unique index* on bookings(slot_id) WHERE status='active' makes it
  physically impossible for two active bookings to share a slot — the booking
  race condition is enforced by the database, not just application checks.
- Timestamps are timezone-aware UTC.
"""
import enum
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(dt):
    """Coerce a possibly-naive datetime (SQLite loses tz info) to aware UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class _StrEnum(str, enum.Enum):
    """Base str-enum that renders as its plain value (so templates show
    'available', not 'SlotStatus.available') while keeping == comparisons."""

    def __str__(self):
        return self.value


class Role(_StrEnum):
    user = "user"
    admin = "admin"


class SlotStatus(_StrEnum):
    available = "available"
    reserved = "reserved"
    occupied = "occupied"


class VehicleType(_StrEnum):
    car = "car"
    bike = "bike"
    truck = "truck"


class BookingStatus(_StrEnum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.user)
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    bookings = db.relationship("Booking", back_populates="user", lazy="dynamic")

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.admin

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and as_utc(self.locked_until) > utcnow()

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role.value}


class ParkingLot(db.Model):
    """A physical parking location with geo-coordinates (multi-lot support)."""
    __tablename__ = "parking_lots"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False, default="")
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    slots = db.relationship("ParkingSlot", back_populates="lot", lazy="dynamic")

    def availability(self):
        avail = self.slots.filter_by(status=SlotStatus.available).count()
        return {"total": self.slots.count(), "available": avail}

    def to_dict(self):
        a = self.availability()
        return {
            "id": self.id, "name": self.name, "address": self.address,
            "latitude": self.latitude, "longitude": self.longitude,
            "total": a["total"], "available": a["available"],
        }


class ParkingSlot(db.Model):
    __tablename__ = "parking_slots"

    id = db.Column(db.Integer, primary_key=True)
    slot_number = db.Column(db.String(16), unique=True, nullable=False, index=True)
    location = db.Column(db.String(120), nullable=False)
    lot_id = db.Column(db.Integer, db.ForeignKey("parking_lots.id"), nullable=True, index=True)
    status = db.Column(db.Enum(SlotStatus), nullable=False, default=SlotStatus.available, index=True)
    vehicle_type = db.Column(db.Enum(VehicleType), nullable=False, default=VehicleType.car)
    base_rate = db.Column(db.Float, nullable=False, default=30.0)
    # Cached surge multiplier (recomputed by the pricing engine).
    surge_multiplier = db.Column(db.Float, nullable=False, default=1.0)
    reserved_until = db.Column(db.DateTime(timezone=True), nullable=True)

    bookings = db.relationship("Booking", back_populates="slot", lazy="dynamic")
    lot = db.relationship("ParkingLot", back_populates="slots")

    @property
    def current_rate(self) -> float:
        return round(self.base_rate * self.surge_multiplier, 2)

    # Backwards-compatible alias used by templates.
    @property
    def rate_per_hour(self) -> float:
        return self.current_rate

    def to_dict(self):
        return {
            "id": self.id,
            "slot_number": self.slot_number,
            "location": self.location,
            "lot_id": self.lot_id,
            "status": self.status.value,
            "vehicle_type": self.vehicle_type.value,
            "base_rate": self.base_rate,
            "current_rate": self.current_rate,
            "surge_multiplier": self.surge_multiplier,
        }


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("parking_slots.id"), nullable=False, index=True)
    vehicle_number = db.Column(db.String(32), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    rate_applied = db.Column(db.Float, nullable=True)
    total_cost = db.Column(db.Float, nullable=True)
    status = db.Column(db.Enum(BookingStatus), nullable=False, default=BookingStatus.active, index=True)

    user = db.relationship("User", back_populates="bookings")
    slot = db.relationship("ParkingSlot", back_populates="bookings")

    # --- Flat accessors so templates can use booking.slot_number etc. ---
    @property
    def start_iso(self):
        """UTC ISO-8601 (with offset) so the browser computes elapsed time
        correctly regardless of the viewer's timezone."""
        return as_utc(self.start_time).isoformat() if self.start_time else ""

    @property
    def slot_number(self):
        return self.slot.slot_number if self.slot else None

    @property
    def location(self):
        return self.slot.location if self.slot else None

    @property
    def vehicle_type(self):
        return self.slot.vehicle_type if self.slot else None

    @property
    def rate_per_hour(self):
        return self.rate_applied if self.rate_applied is not None else (
            self.slot.current_rate if self.slot else 0
        )

    @property
    def user_name(self):
        return self.user.name if self.user else None

    @property
    def user_email(self):
        return self.user.email if self.user else None

    __table_args__ = (
        # The teeth of the concurrency fix: only ONE active booking per slot, ever.
        db.Index(
            "uq_active_booking_per_slot",
            "slot_id",
            unique=True,
            sqlite_where=db.text("status = 'active'"),
            postgresql_where=db.text("status = 'active'"),
        ),
        # Only one active booking per user.
        db.Index(
            "uq_active_booking_per_user",
            "user_id",
            unique=True,
            sqlite_where=db.text("status = 'active'"),
            postgresql_where=db.text("status = 'active'"),
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "slot_id": self.slot_id,
            "vehicle_number": self.vehicle_number,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_minutes": self.duration_minutes,
            "rate_applied": self.rate_applied,
            "total_cost": self.total_cost,
            "status": self.status.value,
        }
