"""Settings: account (profile/password/notifications) + admin system config."""
from app.models import User
from app.services import pricing_service, settings_service


def _login(client, email, pw="Passw0rd1"):
    return client.post("/login", data={"email": email, "password": pw}, follow_redirects=True)


# ---------------- settings_service ----------------
def test_settings_fall_back_to_config_default(app):
    assert settings_service.get("pricing_surge_max") == app.config["PRICING_SURGE_MAX"]


def test_settings_db_override(app, db):
    settings_service.set_many({"pricing_surge_max": "3.5", "pricing_surge_enabled": "off"})
    assert settings_service.get("pricing_surge_max") == 3.5
    assert settings_service.get("pricing_surge_enabled") is False


def test_disabled_surge_returns_flat(app, db):
    settings_service.set_many({"pricing_surge_enabled": "off"})
    assert pricing_service.compute_surge(1.0) == 1.0


# ---------------- account ----------------
def test_settings_page_renders_for_user(auth_client):
    r = auth_client.get("/settings/")
    assert r.status_code == 200 and b"Profile" in r.data
    assert b"System Settings" not in r.data  # non-admin sees no system section


def test_update_profile(auth_client, db):
    auth_client.post("/settings/profile", data={"name": "New Name"}, follow_redirects=True)
    user = db.session.query(User).filter_by(email="driver@test.com").first()
    assert user.name == "New Name"
    assert user.email_notifications is False  # checkbox omitted = off


def test_change_password_flow(auth_client, db):
    # wrong current
    auth_client.post("/settings/password", data={
        "current_password": "wrong", "new_password": "NewPass123", "confirm_password": "NewPass123",
    }, follow_redirects=True)
    user = db.session.query(User).filter_by(email="driver@test.com").first()
    assert user.check_password("Passw0rd1")  # unchanged

    # correct current
    auth_client.post("/settings/password", data={
        "current_password": "Passw0rd1", "new_password": "NewPass123", "confirm_password": "NewPass123",
    }, follow_redirects=True)
    db.session.expire_all()
    user = db.session.query(User).filter_by(email="driver@test.com").first()
    assert user.check_password("NewPass123")


def test_change_password_mismatch(auth_client, db):
    auth_client.post("/settings/password", data={
        "current_password": "Passw0rd1", "new_password": "NewPass123", "confirm_password": "different",
    }, follow_redirects=True)
    user = db.session.query(User).filter_by(email="driver@test.com").first()
    assert user.check_password("Passw0rd1")  # unchanged


# ---------------- admin system settings ----------------
def test_admin_sees_system_section(client):
    _login(client, "admin@parking.com", "admin123")
    r = client.get("/settings/")
    assert r.status_code == 200 and b"System Settings" in r.data


def test_admin_updates_system_settings(client, db):
    _login(client, "admin@parking.com", "admin123")
    client.post("/settings/system", data={
        "pricing_surge_threshold": "0.7", "pricing_surge_max": "2.5",
        "reservation_ttl_minutes": "20", "upi_vpa": "boss@okaxis", "upi_payee_name": "Boss",
        # pricing_surge_enabled omitted = disabled
    }, follow_redirects=True)
    assert settings_service.get("pricing_surge_max") == 2.5
    assert settings_service.get("reservation_ttl_minutes") == 20
    assert settings_service.get("upi_vpa") == "boss@okaxis"
    assert settings_service.get("pricing_surge_enabled") is False


def test_non_admin_cannot_update_system(auth_client):
    r = auth_client.post("/settings/system", data={"pricing_surge_max": "9"}, follow_redirects=False)
    assert r.status_code in (302, 303)  # redirected by admin_required
    # value not changed
    assert settings_service.get("pricing_surge_max") != 9
