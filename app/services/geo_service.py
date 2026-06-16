"""
geo_service.py — geospatial queries for multi-lot parking.

Distance uses the Haversine formula, which is database-agnostic and exact enough
for city-scale "nearest lot" ranking. On PostgreSQL the same query can be pushed
down to PostGIS (`ST_DistanceSphere` over a GEOGRAPHY column with a GiST index)
for large datasets — see compute_distance_km's docstring. For the scale here
(tens of lots), in-process Haversine is simpler and plenty fast.
"""
import math

from ..extensions import db
from ..models import ParkingLot

EARTH_RADIUS_KM = 6371.0088


def compute_distance_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km between two lat/lng points (Haversine).

    Postgres/PostGIS equivalent for scale:
        ORDER BY geom <-> ST_MakePoint(:lon,:lat)::geography  -- KNN GiST index
    """
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def list_lots():
    return db.session.query(ParkingLot).order_by(ParkingLot.name).all()


def nearest_lots(lat: float, lon: float, limit: int = 5):
    """Lots ranked by distance from (lat, lon), each annotated with distance + availability."""
    out = []
    for lot in db.session.query(ParkingLot).all():
        d = compute_distance_km(lat, lon, lot.latitude, lot.longitude)
        data = lot.to_dict()
        data["distance_km"] = round(d, 2)
        out.append(data)
    out.sort(key=lambda x: x["distance_km"])
    return out[:limit]
