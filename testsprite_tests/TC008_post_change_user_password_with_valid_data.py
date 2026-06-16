import requests
import uuid

BASE_URL = "http://localhost:5000"
REGISTER_URL = f"{BASE_URL}/api/v1/auth/register"
LOGIN_URL = f"{BASE_URL}/api/v1/auth/login"
CHANGE_PASSWORD_URL = f"{BASE_URL}/settings/password"
SETTINGS_URL = f"{BASE_URL}/settings/"
TIMEOUT = 30


def test_post_change_user_password_with_valid_data():
    # Register a fresh user
    test_email = f"testuser_{uuid.uuid4()}@example.com"
    test_name = "Test User"
    test_password = "TestPass123!"
    new_password = "NewPass123!"
    headers = {"Content-Type": "application/json"}

    session = requests.Session()

    try:
        # Register user
        reg_payload = {
            "name": test_name,
            "email": test_email,
            "password": test_password
        }
        reg_resp = session.post(REGISTER_URL, json=reg_payload, headers=headers, timeout=TIMEOUT)
        assert reg_resp.status_code == 201 or reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"

        # Login user to get token
        login_payload = {
            "email": test_email,
            "password": test_password
        }
        login_resp = session.post(LOGIN_URL, json=login_payload, headers=headers, timeout=TIMEOUT)
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        login_data = login_resp.json()
        assert "access_token" in login_data, "No access_token in login response"
        token = login_data["access_token"]

        # Retrieve CSRF token by GET /settings/ with auth
        auth_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        settings_get_resp = session.get(SETTINGS_URL, headers=auth_headers, timeout=TIMEOUT)
        assert settings_get_resp.status_code == 200, f"Failed to get settings page: {settings_get_resp.text}"

        # Get CSRF token from cookies
        csrf_token = session.cookies.get('csrf_token') or session.cookies.get('csrf_access_token') or session.cookies.get('XSRF-TOKEN')
        assert csrf_token, "CSRF token cookie not found"

        # Change password
        change_pw_payload = {
            "current_password": test_password,
            "new_password": new_password,
            "confirm_password": new_password
        }
        # Add CSRF token header
        change_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-CSRFToken": csrf_token
        }
        change_resp = session.post(CHANGE_PASSWORD_URL, json=change_pw_payload, headers=change_headers, timeout=TIMEOUT)
        assert change_resp.status_code == 200, f"Password change failed: {change_resp.text}"

        # Try to login with old password - should fail
        login_old_resp = session.post(LOGIN_URL, json=login_payload, headers=headers, timeout=TIMEOUT)
        assert login_old_resp.status_code == 401 or login_old_resp.status_code == 400, "Old password should no longer work"

        # Try to login with new password - should succeed
        login_new_payload = {
            "email": test_email,
            "password": new_password
        }
        login_new_resp = session.post(LOGIN_URL, json=login_new_payload, headers=headers, timeout=TIMEOUT)
        assert login_new_resp.status_code == 200, f"Login with new password failed: {login_new_resp.text}"
        login_new_data = login_new_resp.json()
        assert "access_token" in login_new_data, "No access_token after password change login"
    finally:
        # Cleanup: There is no endpoint provided to delete user, so nothing to cleanup.
        pass

test_post_change_user_password_with_valid_data()
