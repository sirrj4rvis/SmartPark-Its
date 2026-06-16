"""End-to-end web route tests (Jinja flows) for user + admin blueprints."""
from app.models import Booking, BookingStatus, ParkingSlot


def _login(client, email, pw="Passw0rd1"):
    return client.post("/login", data={"email": email, "password": pw}, follow_redirects=True)


# ---------------- public / auth ----------------
def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200 and b"SmartPark" in r.data


def test_logout_clears_session(auth_client):
    r = auth_client.get("/logout", follow_redirects=True)
    assert r.status_code == 200
    # dashboard now redirects to login
    assert auth_client.get("/dashboard", follow_redirects=False).status_code in (302, 303)


# ---------------- user flows ----------------
def test_dashboard_shows_slots(auth_client):
    r = auth_client.get("/dashboard")
    assert r.status_code == 200 and b"Parking Dashboard" in r.data


def test_full_booking_web_flow(auth_client, first_slot, db):
    # book
    r = auth_client.post(f"/book/{first_slot.id}",
                         data={"vehicle_number": "KA01AB1234"}, follow_redirects=True)
    assert r.status_code == 200
    booking = db.session.query(Booking).filter_by(status=BookingStatus.active).first()
    assert booking is not None
    # my bookings
    assert auth_client.get("/my_bookings").status_code == 200
    # exit -> receipt
    r = auth_client.post(f"/exit/{booking.id}", follow_redirects=True)
    assert r.status_code == 200 and b"Receipt" in r.data
    # receipt page directly
    assert auth_client.get(f"/receipt/{booking.id}").status_code == 200


def test_book_nonexistent_slot(auth_client):
    r = auth_client.get("/book/99999", follow_redirects=True)
    assert r.status_code == 200  # redirected back to dashboard with flash


def test_booking_page_renders(auth_client, first_slot):
    r = auth_client.get(f"/book/{first_slot.id}")
    assert r.status_code == 200 and b"Book Your Slot" in r.data


# ---------------- admin flows ----------------
def test_admin_dashboard_and_analytics(client):
    _login(client, "admin@parking.com", "admin123")
    assert client.get("/admin/").status_code == 200
    assert client.get("/admin/analytics").status_code == 200
    assert client.get("/admin/slots").status_code == 200
    assert client.get("/admin/bookings").status_code == 200


def test_admin_add_toggle_delete_slot(client, db):
    _login(client, "admin@parking.com", "admin123")
    client.post("/admin/slots/add", data={
        "slot_number": "Z9", "location": "Test", "vehicle_type": "car", "rate_per_hour": "20"
    }, follow_redirects=True)
    slot = db.session.query(ParkingSlot).filter_by(slot_number="Z9").first()
    assert slot is not None
    # toggle
    client.post(f"/admin/slots/toggle/{slot.id}", follow_redirects=True)
    db.session.expire_all()
    assert db.session.get(ParkingSlot, slot.id).status.value == "occupied"
    client.post(f"/admin/slots/toggle/{slot.id}", follow_redirects=True)
    # delete
    client.post(f"/admin/slots/delete/{slot.id}", follow_redirects=True)
    assert db.session.get(ParkingSlot, slot.id) is None


def test_admin_bookings_search(client, db, make_user):
    from app.services import booking_service
    _login(client, "admin@parking.com", "admin123")
    user = make_user(email="searcher@test.com")
    slot = db.session.query(ParkingSlot).first()
    booking_service.book_slot(user.id, slot.id, "SEARCHME99")
    r = client.get("/admin/bookings?q=SEARCHME")
    assert r.status_code == 200 and b"SEARCHME99" in r.data


def test_non_admin_blocked_from_admin(auth_client):
    assert auth_client.get("/admin/", follow_redirects=False).status_code in (302, 303)
    assert auth_client.get("/admin/analytics", follow_redirects=False).status_code in (302, 303)
