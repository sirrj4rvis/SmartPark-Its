"""Geospatial: distance math, nearest-lot ranking, lots API, map page."""
from app.services import geo_service


def test_haversine_known_distance():
    # Bengaluru (MSRIT) to MG Road ~ a few km; sanity bounds.
    d = geo_service.compute_distance_km(13.0297, 77.5645, 12.9756, 77.6068)
    assert 5 < d < 9
    # Same point = 0.
    assert geo_service.compute_distance_km(13.0, 77.0, 13.0, 77.0) == 0.0


def test_seeded_lots_exist(app):
    lots = geo_service.list_lots()
    assert len(lots) == 3
    assert all(l.latitude and l.longitude for l in lots)


def test_nearest_lots_ordering(app):
    # A point right at MSRIT should rank MSRIT lot first.
    near = geo_service.nearest_lots(13.0297, 77.5645, limit=3)
    assert near[0]["name"].startswith("MSRIT")
    dists = [l["distance_km"] for l in near]
    assert dists == sorted(dists)


def test_lots_carry_availability(app):
    lots = geo_service.list_lots()
    total = sum(l.to_dict()["total"] for l in lots)
    assert total == 15  # all demo slots assigned to a lot


def test_api_lots_and_nearest(client):
    r = client.get("/api/v1/lots")
    assert r.status_code == 200 and len(r.get_json()["lots"]) == 3

    r = client.get("/api/v1/lots/nearest?lat=13.0297&lng=77.5645")
    assert r.status_code == 200
    assert "distance_km" in r.get_json()["lots"][0]

    # Missing params -> 400
    assert client.get("/api/v1/lots/nearest").status_code == 400


def test_map_page_renders(client):
    r = client.get("/map")
    assert r.status_code == 200 and b"Find Parking" in r.data
