import requests
import uuid

BASE_URL = "http://localhost:5000"
REGISTER_ENDPOINT = "/api/v1/auth/register"
LOGIN_ENDPOINT = "/api/v1/auth/login"
BOOKINGS_ENDPOINT = "/api/v1/bookings"

TIMEOUT = 30


def test_post_book_parking_slot_with_valid_vehicle_number():
    session = requests.Session()
    # Step 1: Register a new user
    name = "Test User"
    # Unique email for each test run
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    password = "validpass123"

    register_payload = {
        "name": name,
        "email": email,
        "password": password
    }

    resp = session.post(f"{BASE_URL}{REGISTER_ENDPOINT}", json=register_payload, timeout=TIMEOUT)
    assert resp.status_code == 201 or resp.status_code == 200, f"Registration failed: {resp.text}"

    # Step 2: Login with registered user to get JWT token
    login_payload = {
        "email": email,
        "password": password
    }

    resp = session.post(f"{BASE_URL}{LOGIN_ENDPOINT}", json=login_payload, timeout=TIMEOUT)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    login_data = resp.json()
    assert "access_token" in login_data, "No access_token in login response"
    token = login_data["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Step 3: Get list of available slots to book from /api/v1/slots
    slots_resp = session.get(f"{BASE_URL}/api/v1/slots", headers=headers, timeout=TIMEOUT)
    assert slots_resp.status_code == 200, f"Fetching slots failed: {slots_resp.text}"
    slots_data = slots_resp.json()

    # Adjust slots_data processing to handle dict response
    if isinstance(slots_data, dict):
        # Find list of slots in dict values
        possible_lists = [v for v in slots_data.values() if isinstance(v, list)]
        assert possible_lists, "No list found in slots response object"
        slots_list = possible_lists[0]
    elif isinstance(slots_data, list):
        slots_list = slots_data
    else:
        assert False, "Slots response is neither a list nor dict containing list"

    available_slots = [slot for slot in slots_list if slot.get("status") == "available" or slot.get("is_available") is True or slot.get("available") is True]
    assert len(available_slots) > 0, "No available parking slots to book"
    slot_id = available_slots[0]["id"]

    # Step 4: Book parking slot with valid vehicle number
    booking_payload = {
        "slot_id": slot_id,
        "vehicle_number": "AB123CD"
    }

    booking_id = None
    try:
        resp = session.post(f"{BASE_URL}{BOOKINGS_ENDPOINT}", json=booking_payload, headers=headers, timeout=TIMEOUT)
        assert resp.status_code == 201 or resp.status_code == 200, f"Booking failed: {resp.text}"
        booking_resp_data = resp.json()
        assert booking_resp_data.get("slot_id") == slot_id, "Booked slot_id mismatch"
        assert booking_resp_data.get("vehicle_number") == "AB123CD", "Vehicle number mismatch"
        booking_id = booking_resp_data.get("id")
        assert booking_id is not None, "No booking id returned"

        # Step 5: Confirm booking is reflected in user's bookings
        user_bookings_resp = session.get(f"{BASE_URL}{BOOKINGS_ENDPOINT}", headers=headers, timeout=TIMEOUT)
        assert user_bookings_resp.status_code == 200, f"Fetching user bookings failed: {user_bookings_resp.text}"
        bookings_resp_data = user_bookings_resp.json()
        # Adjust if bookings_resp_data is dict containing bookings list
        if isinstance(bookings_resp_data, dict):
            possible_lists = [v for v in bookings_resp_data.values() if isinstance(v, list)]
            assert possible_lists, "No list found in user bookings response object"
            bookings_list = possible_lists[0]
        elif isinstance(bookings_resp_data, list):
            bookings_list = bookings_resp_data
        else:
            assert False, "User bookings response is neither a list nor dict containing list"

        assert isinstance(bookings_list, list), "User bookings response is not a list"
        booked_slots = [b for b in bookings_list if b.get("id") == booking_id]
        assert len(booked_slots) == 1, "New booking not found in user bookings"
        booked_slot = booked_slots[0]
        assert booked_slot.get("slot_id") == slot_id, "Booked slot_id mismatch in user bookings"
        assert booked_slot.get("vehicle_number") == "AB123CD", "Vehicle number mismatch in user bookings"

    finally:
        # Cleanup: Exit/end the booking to release the slot if booking was done
        if booking_id:
            exit_resp = session.post(f"{BASE_URL}{BOOKINGS_ENDPOINT}/{booking_id}/exit", headers=headers, timeout=TIMEOUT)
            assert exit_resp.status_code == 200, f"Exit booking failed: {exit_resp.text}"


test_post_book_parking_slot_with_valid_vehicle_number()
