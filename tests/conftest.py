"""Shared pytest fixtures."""
import pytest

from app import create_app
from app.cli import seed_data
from app.extensions import db as _db
from config import TestingConfig


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        _db.create_all()
        seed_data()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_user(app):
    from app.models import Role, User

    def _make(email="u@test.com", password="Passw0rd1", name="Test User", role=Role.user):
        user = User(name=name, email=email, role=role)
        user.set_password(password)
        _db.session.add(user)
        _db.session.commit()
        return user

    return _make


@pytest.fixture()
def auth_client(client, make_user):
    """A client logged in as a regular user."""
    make_user(email="driver@test.com")
    client.post("/login", data={"email": "driver@test.com", "password": "Passw0rd1"})
    return client


@pytest.fixture()
def first_slot(app):
    from app.models import ParkingSlot

    return _db.session.query(ParkingSlot).order_by(ParkingSlot.id).first()
