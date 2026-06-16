import requests
import uuid

BASE_URL = "http://localhost:5000"
ADMIN_EMAIL = "admin@parking.com"
ADMIN_PASSWORD = "admin123"
TIMEOUT = 30

def get_admin_token():
    url = f"{BASE_URL}/api/v1/auth/login"
    payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    resp = requests.post(url, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("access_token")

def create_parking_slot(token):
    url = f"{BASE_URL}/admin/slots/add"
    # Create a slot with a unique name to avoid clashes
    slot_name = f"test-slot-{uuid.uuid4()}"
    payload = {"name": slot_name}
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(url, data=payload, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    slot = resp.json()
    assert "id" in slot and "status" in slot
    return slot

def delete_parking_slot(token, slot_id):
    url = f"{BASE_URL}/admin/slots/delete/{slot_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()

def get_parking_slot(token, slot_id):
    url = f"{BASE_URL}/api/v1/slots"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    slots = resp.json()
    for s in slots:
        if s.get("id") == slot_id:
            return s
    return None

def toggle_parking_slot(token, slot_id):
    url = f"{BASE_URL}/admin/slots/toggle/{slot_id}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()

def test_post_admin_toggle_parking_slot_status():
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    slot = create_parking_slot(token)
    slot_id = slot["id"]
    original_status = slot["status"]

    try:
        # Toggle slot status via admin endpoint
        toggled_slot = toggle_parking_slot(token, slot_id)
        assert toggled_slot.get("id") == slot_id
        assert "status" in toggled_slot
        new_status = toggled_slot["status"]
        assert new_status != original_status, "Slot status was not toggled"

        # Verify the slot status changed in the system by fetching slots list
        fetched_slot = get_parking_slot(token, slot_id)
        assert fetched_slot is not None, "Slot not found after toggle"
        assert fetched_slot["status"] == new_status, "Slot status not updated correctly in system"
    finally:
        # Clean up by deleting the created slot
        delete_parking_slot(token, slot_id)

test_post_admin_toggle_parking_slot_status()
