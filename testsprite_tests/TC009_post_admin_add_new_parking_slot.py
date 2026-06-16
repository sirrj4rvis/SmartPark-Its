import requests
import uuid

BASE_URL = "http://localhost:5000"
LOGIN_URL = f"{BASE_URL}/api/v1/auth/login"
ADMIN_SLOTS_URL = f"{BASE_URL}/admin/slots"
SLOTS_URL = f"{BASE_URL}/api/v1/slots"
TIMEOUT = 30

ADMIN_EMAIL = "admin@parking.com"
ADMIN_PASSWORD = "admin123"


def get_admin_token():
    try:
        resp = requests.post(
            LOGIN_URL,
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token")
    except Exception as e:
        raise RuntimeError(f"Failed to obtain admin token: {e}")


def test_post_admin_add_new_parking_slot():
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Create a unique slot identifier to avoid duplicates
    slot_name = f"TestSlot-{uuid.uuid4()}"
    slot_payload = {
        "name": slot_name,
        "location": "Test Location",
        "description": "Slot created by automated test",
    }
    slot_id = None

    try:
        # Add new parking slot via admin endpoint
        add_slot_resp = requests.post(
            f"{ADMIN_SLOTS_URL}/add",
            json=slot_payload,
            headers=headers,
            timeout=TIMEOUT,
        )
        assert add_slot_resp.status_code == 201, f"Slot creation failed: {add_slot_resp.text}"
        add_resp_json = add_slot_resp.json()
        slot_id = add_resp_json.get("id")
        assert slot_id is not None, "Returned slot ID is None"

        # Verify the new slot appears in the slot list
        list_resp = requests.get(SLOTS_URL, headers=headers, timeout=TIMEOUT)
        assert list_resp.status_code == 200, f"Failed to get slots list: {list_resp.text}"
        slots = list_resp.json()
        # Confirm the slot with slot_id exists and is available for booking
        matched_slots = [s for s in slots if s.get("id") == slot_id]
        assert matched_slots, f"Created slot ID {slot_id} not found in slot list"
        slot_info = matched_slots[0]
        # Check slot is available for booking: typically a key like 'available' or status
        # Assuming slot has an 'available' boolean field
        assert slot_info.get("available") is True or slot_info.get("status", "").lower() == "available", \
            "Newly added slot is not available for booking"

    finally:
        # Clean up: delete the created slot if created
        if slot_id is not None:
            try:
                del_resp = requests.post(
                    f"{ADMIN_SLOTS_URL}/delete/{slot_id}",
                    headers=headers,
                    timeout=TIMEOUT,
                )
                # Accept 200 or 204 as success
                assert del_resp.status_code in (200, 204), f"Slot deletion failed: {del_resp.text}"
            except Exception:
                pass


test_post_admin_add_new_parking_slot()