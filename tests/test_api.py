"""REST API v1 + JWT."""


def _token(client, email="admin@parking.com", password="admin123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.get_json()["access_token"]


def test_api_register_returns_token(client, db):
    r = client.post("/api/v1/auth/register",
                    json={"name": "Api User", "email": "apinew@test.com", "password": "Passw0rd1"})
    assert r.status_code == 201
    assert r.get_json()["access_token"]


def test_api_register_rejects_short_password(client):
    r = client.post("/api/v1/auth/register",
                    json={"name": "X", "email": "x@test.com", "password": "short"})
    assert r.status_code == 400


def test_api_register_duplicate_email(client, make_user):
    make_user(email="dupe@test.com")
    r = client.post("/api/v1/auth/register",
                    json={"name": "Dupe", "email": "dupe@test.com", "password": "Passw0rd1"})
    assert r.status_code == 409


def test_public_slots_endpoint(client):
    r = client.get("/api/v1/slots")
    assert r.status_code == 200
    body = r.get_json()
    assert "slots" in body and "counts" in body


def test_openapi_spec_served(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert r.get_json()["openapi"].startswith("3.")


def test_jwt_required_for_bookings(client):
    assert client.get("/api/v1/bookings").status_code == 401


def test_full_api_booking_flow(client, make_user, first_slot):
    make_user(email="api@test.com", password="Passw0rd1")
    token = _token(client, "api@test.com", "Passw0rd1")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/bookings",
                    json={"slot_id": first_slot.id, "vehicle_number": "KA01AB1234"},
                    headers=headers)
    assert r.status_code == 201
    booking_id = r.get_json()["id"]

    r = client.get("/api/v1/bookings", headers=headers)
    assert r.status_code == 200 and len(r.get_json()["bookings"]) == 1

    r = client.post(f"/api/v1/bookings/{booking_id}/exit", headers=headers)
    assert r.status_code == 200 and r.get_json()["total_cost"] is not None


def test_analytics_requires_admin(client, make_user):
    make_user(email="plain@test.com", password="Passw0rd1")
    token = _token(client, "plain@test.com", "Passw0rd1")
    r = client.get("/api/v1/analytics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403

    admin_token = _token(client)
    r = client.get("/api/v1/analytics", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
