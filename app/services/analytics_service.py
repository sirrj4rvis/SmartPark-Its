"""
analytics_service.py — aggregations powering the admin analytics dashboard.

Returns chart-ready series for revenue trend, occupancy, peak hours, and
vehicle-type mix. Pure read queries; safe to cache.
"""
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func

from ..extensions import db
from ..models import Booking, BookingStatus, ParkingSlot, User, Role, utcnow


def kpis():
    total_slots = db.session.query(ParkingSlot).count()
    total_users = db.session.query(User).filter_by(role=Role.user).count()
    total_bookings = db.session.query(Booking).count()
    active_bookings = db.session.query(Booking).filter_by(status=BookingStatus.active).count()
    revenue = (
        db.session.query(func.coalesce(func.sum(Booking.total_cost), 0.0))
        .filter(Booking.status == BookingStatus.completed)
        .scalar()
    ) or 0.0
    return {
        "total_slots": total_slots,
        "total_users": total_users,
        "total_bookings": total_bookings,
        "active_bookings": active_bookings,
        "revenue": round(revenue, 2),
    }


def revenue_trend(days: int = 14):
    """Daily completed-booking revenue for the last `days` days."""
    since = utcnow() - timedelta(days=days)
    rows = (
        db.session.query(Booking.end_time, Booking.total_cost)
        .filter(Booking.status == BookingStatus.completed, Booking.end_time >= since)
        .all()
    )
    buckets = defaultdict(float)
    for end_time, cost in rows:
        if end_time:
            buckets[end_time.date().isoformat()] += cost or 0.0
    labels, values = [], []
    for i in range(days - 1, -1, -1):
        d = (utcnow() - timedelta(days=i)).date().isoformat()
        labels.append(d)
        values.append(round(buckets.get(d, 0.0), 2))
    return {"labels": labels, "values": values}


def peak_hours():
    """Booking volume by hour-of-day (0..23) — the demand heatmap."""
    rows = db.session.query(Booking.start_time).all()
    hist = [0] * 24
    for (start,) in rows:
        if start:
            hist[start.hour] += 1
    return {"labels": [f"{h:02d}:00" for h in range(24)], "values": hist}


def vehicle_mix():
    rows = (
        db.session.query(ParkingSlot.vehicle_type, func.count(ParkingSlot.id))
        .group_by(ParkingSlot.vehicle_type)
        .all()
    )
    return {"labels": [vt.value for vt, _ in rows], "values": [c for _, c in rows]}


def occupancy_gauge():
    total = db.session.query(ParkingSlot).count() or 1
    occupied = (
        db.session.query(ParkingSlot)
        .filter(ParkingSlot.status != "available")
        .count()
    )
    return {"occupied": occupied, "free": total - occupied, "ratio": round(occupied / total, 3)}
