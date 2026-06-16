import requests
import uuid

BASE_URL = "http://localhost:5000"
TIMEOUT = 30


def get_auth_token(email: str, password: str) -> str:
    url = f"{BASE_URL}/api/v1/auth/login"
    payload = {"email": email, "password": password}
    response = requests.post(url, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    token = response.json().get("access_token")
    assert token and isinstance(token, str)
    return token


def register_user(name: str, email: str, password: str) -> dict:
    url = f"{BASE_URL}/api/v1/auth/register"
    payload = {"name": name, "email": email, "password": password}
    response = requests.post(url, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def delete_user(token: str):
    # No deletion endpoint available in PRD
    pass


def test_post_update_user_profile_settings():
    unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    user_name = "Test User"
    user_password = "StrongPass123"
    token = None

    try:
        reg_response = register_user(user_name, unique_email, user_password)
        assert "id" in reg_response and isinstance(reg_response["id"], int)

        token = get_auth_token(unique_email, user_password)
        headers = {"Authorization": f"Bearer {token}"}

        updated_name = "Updated Name"
        updated_email = f"updated_{unique_email}"
        email_notifications = True

        profile_update_payload = {
            "name": updated_name,
            "email": updated_email,
            "email_notifications": email_notifications
        }

        url_profile_update = f"{BASE_URL}/settings/profile"
        resp_update = requests.post(
            url_profile_update, json=profile_update_payload, headers=headers, timeout=TIMEOUT
        )
        assert resp_update.status_code == 200, f"Expected 200, got {resp_update.status_code}"
        data_update = resp_update.json()
        assert "name" in data_update and data_update["name"] == updated_name
        assert "email" in data_update and data_update["email"] == updated_email
        assert "email_notifications" in data_update and data_update["email_notifications"] == email_notifications

    finally:
        if token:
            delete_user(token)


test_post_update_user_profile_settings()
