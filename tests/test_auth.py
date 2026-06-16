"""Auth: registration, login, lockout."""
from app.models import User, as_utc, utcnow
from app.security import authenticate


def test_register_creates_user(client, db):
    resp = client.post(
        "/register",
        data={"name": "Alice", "email": "alice@test.com", "password": "Secret123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert db.session.query(User).filter_by(email="alice@test.com").first() is not None


def test_register_rejects_short_password(client, db):
    client.post("/register", data={"name": "Bob", "email": "bob@test.com", "password": "short"})
    assert db.session.query(User).filter_by(email="bob@test.com").first() is None


def test_password_is_hashed(make_user):
    user = make_user(email="hash@test.com", password="Passw0rd1")
    assert user.password_hash != "Passw0rd1"
    assert user.check_password("Passw0rd1")


def test_login_success_and_failure(make_user):
    make_user(email="login@test.com", password="Passw0rd1")
    user, err = authenticate("login@test.com", "Passw0rd1")
    assert user and err is None
    user, err = authenticate("login@test.com", "wrong")
    assert user is None and err


def test_account_lockout_after_max_attempts(app, make_user, db):
    make_user(email="lock@test.com", password="Passw0rd1")
    max_attempts = app.config["LOGIN_MAX_ATTEMPTS"]
    for _ in range(max_attempts):
        authenticate("lock@test.com", "wrong")
    # Even the correct password is now refused while locked.
    user, err = authenticate("lock@test.com", "Passw0rd1")
    assert user is None and "locked" in err.lower()
    locked = db.session.query(User).filter_by(email="lock@test.com").first()
    assert locked.locked_until is not None and as_utc(locked.locked_until) > utcnow()
