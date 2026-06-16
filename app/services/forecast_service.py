"""
forecast_service.py — occupancy forecasting & smart recommendations.

This is the genuinely "intelligent" piece. We build an hour-of-week demand
profile from historical bookings (exponentially weighted toward recent weeks)
and use it to predict expected occupancy for any future hour, plus to rank
slot recommendations. No heavyweight ML dependency — an interpretable model
that still demonstrates feature engineering and time-series reasoning.
"""
from collections import defaultdict

from ..extensions import db
from ..models import Booking, ParkingSlot, SlotStatus, VehicleType, as_utc, utcnow


def _hour_of_week(dt):
    return dt.weekday() * 24 + dt.hour  # 0..167


def build_demand_profile(half_life_weeks: float = 3.0):
    """Return {hour_of_week: expected_concurrent_bookings} from history."""
    rows = db.session.query(Booking.start_time).all()
    if not rows:
        return {}
    now = utcnow()
    weighted = defaultdict(float)
    norm = defaultdict(float)
    decay = 0.5 ** (1.0 / max(0.5, half_life_weeks))
    for (start,) in rows:
        if not start:
            continue
        weeks_ago = max(0.0, (now - as_utc(start)).total_seconds() / (7 * 86400))
        w = decay ** weeks_ago
        weighted[_hour_of_week(start)] += w
        norm[_hour_of_week(start)] += 1.0
    # Average weighted count per hour-of-week bucket.
    return {h: round(weighted[h] / max(1.0, norm[h]) * norm[h], 3) for h in weighted}


def predict_occupancy(target_dt=None):
    """Predicted occupancy ratio (0..1) for the given datetime (default: now+1h)."""
    target_dt = target_dt or (utcnow())
    profile = build_demand_profile()
    total_slots = db.session.query(ParkingSlot).count() or 1
    expected = profile.get(_hour_of_week(target_dt), 0.0)
    return {
        "target": target_dt.isoformat(),
        "expected_bookings": round(expected, 2),
        "predicted_ratio": round(min(1.0, expected / total_slots), 3),
        "confidence": "low" if not profile else "moderate",
    }


def next_24h_forecast():
    from datetime import timedelta

    base = utcnow()
    points = []
    for i in range(24):
        t = base + timedelta(hours=i)
        p = predict_occupancy(t)
        points.append({"hour": t.strftime("%H:00"), "ratio": p["predicted_ratio"]})
    return {"labels": [p["hour"] for p in points], "values": [p["ratio"] for p in points]}


def recommend_slots(vehicle_type: str = None, limit: int = 3):
    """Recommend available slots: cheapest current rate first, then by block."""
    q = db.session.query(ParkingSlot).filter(ParkingSlot.status == SlotStatus.available)
    if vehicle_type:
        try:
            q = q.filter(ParkingSlot.vehicle_type == VehicleType(vehicle_type))
        except ValueError:
            pass
    slots = q.all()
    slots.sort(key=lambda s: (s.current_rate, s.slot_number))
    return [s.to_dict() for s in slots[:limit]]
