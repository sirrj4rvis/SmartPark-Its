"""
pricing_service.py — dynamic / surge pricing engine.

The "Intelligent" in ITS: the rate a driver pays scales with live demand.
When occupancy crosses a threshold, a surge multiplier ramps linearly up to a
configured cap. This makes pricing a real, defensible design discussion
(elasticity, fairness, caps) instead of a hardcoded constant.
"""
from ..extensions import db
from ..models import ParkingSlot, SlotStatus
from . import settings_service


def compute_surge(occupancy_ratio: float) -> float:
    """Map occupancy (0..1) to a surge multiplier in [1.0, PRICING_SURGE_MAX]."""
    if not settings_service.get("pricing_surge_enabled"):
        return 1.0
    threshold = settings_service.get("pricing_surge_threshold")
    cap = settings_service.get("pricing_surge_max")
    if occupancy_ratio <= threshold:
        return 1.0
    # Linear ramp from threshold..1.0 mapped onto 1.0..cap
    span = max(1e-6, 1.0 - threshold)
    ratio = (occupancy_ratio - threshold) / span
    return round(1.0 + ratio * (cap - 1.0), 2)


def current_occupancy_ratio() -> float:
    total = db.session.query(ParkingSlot).count()
    if total == 0:
        return 0.0
    free = db.session.query(ParkingSlot).filter_by(status=SlotStatus.available).count()
    return round((total - free) / total, 4)


def reprice_all() -> float:
    """Recompute and persist surge for every slot. Returns the multiplier used."""
    ratio = current_occupancy_ratio()
    multiplier = compute_surge(ratio)
    db.session.query(ParkingSlot).update(
        {ParkingSlot.surge_multiplier: multiplier}, synchronize_session=False
    )
    db.session.commit()
    return multiplier
