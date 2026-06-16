"""Admin guards, slot CRUD, health/observability."""


def _login_admin(client):
    client.post("/login", data={"email": "admin@parking.com", "password": "admin123"})


def test_admin_routes_require_admin(auth_client):
    # auth_client is a regular user; admin area should redirect away.
    r = auth_client.get("/admin/", follow_redirects=False)
    assert r.status_code in (302, 303)


def test_admin_can_add_and_delete_slot(client, db):
    from app.models import ParkingSlot

    _login_admin(client)
    client.post("/admin/slots/add", data={
        "slot_number": "Z9", "location": "Test Block", "vehicle_type": "car", "rate_per_hour": "25"
    }, follow_redirects=True)
    slot = db.session.query(ParkingSlot).filter_by(slot_number="Z9").first()
    assert slot is not None

    client.post(f"/admin/slots/delete/{slot.id}", follow_redirects=True)
    assert db.session.get(ParkingSlot, slot.id) is None


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200


def test_404_renders_error_page(client):
    r = client.get("/this-does-not-exist")
    assert r.status_code == 404
