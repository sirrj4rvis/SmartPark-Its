import requests
import uuid

BASE_URL = "http://localhost:5000"
TIMEOUT = 30

def test_post_exit_active_booking_and_view_receipt():
    session = requests.Session()

    # Helper to register a fresh user and return email, password
    def register_user():
        unique_id = str(uuid.uuid4())
        user_data = {
            "name": "Test User",
            "email": f"testuser_{unique_id}@example.com",
            "password": "testpassword123"
        }
        r = session.post(f"{BASE_URL}/api/v1/auth/register", json=user_data, timeout=TIMEOUT)
        assert r.status_code == 201, f"User registration failed: {r.text}"
        return user_data["email"], user_data["password"]

    # Helper to login user via form to get session cookies
    def login_user(email, password):
        login_data = {"email": email, "password": password}
        r = session.post(f"{BASE_URL}/login", data=login_data, timeout=TIMEOUT)
        # Redirect to dashboard means login success
        assert r.status_code in [200, 302], f"Login failed: {r.text}"

    # Helper to get available parking slots and return an available slot id
    def get_available_slot(headers):
        r = session.get(f"{BASE_URL}/api/v1/slots", headers=headers, timeout=TIMEOUT)
        assert r.status_code == 200, f"Failed to get slots: {r.text}"
        resp_json = r.json()
        slots = resp_json.get("slots")
        assert isinstance(slots, list), "Slots response 'slots' field is not a list"
        for slot in slots:
            if slot.get("status") == "available" or slot.get("is_available") is True:
                return slot["id"]
        return None

    # Register and login user
    email, password = register_user()
    login_user(email, password)

    # Login via API to get token for booking creation
    login_api_data = {"email": email, "password": password}
    r = session.post(f"{BASE_URL}/api/v1/auth/login", json=login_api_data, timeout=TIMEOUT)
    assert r.status_code == 200, f"API Login failed: {r.text}"
    token = r.json().get("access_token")
    assert token, "No access_token in login response"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    booking_id = None

    try:
        slot_id = get_available_slot(headers)
        assert slot_id is not None, "No available slots found for booking"

        vehicle_number = "TEST1234"
        booking_payload = {"slot_id": slot_id, "vehicle_number": vehicle_number}
        booking_resp = session.post(f"{BASE_URL}/api/v1/bookings", json=booking_payload, headers=headers, timeout=TIMEOUT)
        assert booking_resp.status_code == 201, f"Failed to create booking: {booking_resp.text}"
        booking_data = booking_resp.json()
        booking_id = booking_data.get("id")
        assert booking_id is not None, "Booking ID not returned"

        # Post to exit endpoint with session and CSRF handled by session cookies
        exit_resp = session.post(f"{BASE_URL}/exit/{booking_id}", timeout=TIMEOUT)
        assert exit_resp.status_code == 200, f"Exit booking failed: {exit_resp.text}"

        exit_data = exit_resp.json()
        assert exit_data.get("status") in ["ended", "completed"], "Booking status not ended/completed after exit"
        assert "receipt" in exit_data, "Receipt details missing in exit response"
        receipt = exit_data["receipt"]

        assert "total_amount" in receipt, "Receipt missing total_amount"
        assert "duration" in receipt, "Receipt missing duration"
        assert "slot_id" in receipt and receipt["slot_id"] == slot_id, "Receipt slot_id mismatch"
        assert "vehicle_number" in receipt and receipt["vehicle_number"] == vehicle_number, "Receipt vehicle_number mismatch"

        # Optionally test viewing receipt endpoint
        receipt_resp = session.get(f"{BASE_URL}/receipt/{booking_id}", timeout=TIMEOUT)
        assert receipt_resp.status_code == 200, f"Failed to get receipt: {receipt_resp.text}"
        receipt_view = receipt_resp.json()
        assert receipt_view == receipt or receipt_view.get("total_amount") == receipt.get("total_amount"), "Receipt data mismatch on view"

    finally:
        if booking_id is not None:
            try:
                session.post(f"{BASE_URL}/exit/{booking_id}", timeout=TIMEOUT)
            except Exception:
                pass

test_post_exit_active_booking_and_view_receipt()
