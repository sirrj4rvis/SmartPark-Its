"""
Integration tests against a REAL PostgreSQL (via testcontainers).

These prove the behaviour that SQLite can't: true concurrent bookers racing for
the same slot, serialized by SELECT ... FOR UPDATE and back-stopped by the
partial unique index. Skipped automatically when Docker is unavailable (e.g. a
laptop without a daemon); they run in CI where Docker is present.
"""
import os
import threading

import pytest

pytestmark = pytest.mark.integration

# Skip cleanly if Docker / testcontainers aren't available.
docker_available = True
skip_reason = ""
try:
    from testcontainers.postgres import PostgresContainer
except Exception as exc:  # pragma: no cover
    docker_available = False
    skip_reason = f"testcontainers not importable: {exc}"


@pytest.fixture(scope="module")
def pg_url():
    if not docker_available:
        pytest.skip(skip_reason)
    try:
        with PostgresContainer("postgres:16-alpine") as pg:
            raw = pg.get_connection_url()  # postgresql+psycopg2://...
            # Force psycopg v3 driver (what we ship).
            url = raw.replace("postgresql+psycopg2://", "postgresql+psycopg://")
            yield url
    except Exception as exc:  # Docker daemon down, image pull failure, etc.
        pytest.skip(f"Docker unavailable: {exc}")


@pytest.fixture()
def pg_app(pg_url):
    os.environ["DATABASE_URL"] = pg_url
    from config import BaseConfig
    from app import create_app
    from app.extensions import db
    from app.cli import seed_data

    class PgTestConfig(BaseConfig):
        TESTING = True
        WTF_CSRF_ENABLED = False
        RATELIMIT_ENABLED = False
        CACHE_TYPE = "SimpleCache"
        SQLALCHEMY_DATABASE_URI = pg_url

    app = create_app(PgTestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_data()
    yield app
    with app.app_context():
        db.drop_all()


def test_partial_unique_index_exists_on_postgres(pg_app):
    from sqlalchemy import text
    from app.extensions import db

    with pg_app.app_context():
        row = db.session.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_active_booking_per_slot'")
        ).fetchone()
        assert row is not None
        assert "WHERE" in row[0].upper() and "ACTIVE" in row[0].upper()


def test_concurrent_bookings_only_one_wins(pg_app):
    """50 threads race for the same slot; exactly one active booking may exist."""
    from app.extensions import db
    from app.models import Booking, BookingStatus, ParkingSlot, User, Role
    from app.services import booking_service

    with pg_app.app_context():
        slot_id = db.session.query(ParkingSlot).first().id
        # Create 50 distinct users.
        users = []
        for i in range(50):
            u = User(name=f"U{i}", email=f"race{i}@test.com", role=Role.user)
            u.set_password("Passw0rd1")
            db.session.add(u)
            users.append(u)
        db.session.commit()
        user_ids = [u.id for u in users]

    results = {"ok": 0, "rejected": 0}
    lock = threading.Lock()

    def attempt(uid):
        with pg_app.app_context():
            try:
                booking_service.book_slot(uid, slot_id, f"KA01AB{uid:04d}")
                with lock:
                    results["ok"] += 1
            except Exception:
                with lock:
                    results["rejected"] += 1

    threads = [threading.Thread(target=attempt, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with pg_app.app_context():
        active = (
            db.session.query(Booking)
            .filter_by(slot_id=slot_id, status=BookingStatus.active)
            .count()
        )

    assert active == 1, f"expected exactly 1 active booking, found {active}"
    assert results["ok"] == 1, f"expected 1 success, got {results}"
