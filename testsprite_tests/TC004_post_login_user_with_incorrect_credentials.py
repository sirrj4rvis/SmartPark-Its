import requests

BASE_URL = "http://localhost:5000"
LOGIN_ENDPOINT = "/api/v1/auth/login"
TIMEOUT = 30

def test_post_login_user_with_incorrect_credentials():
    url = BASE_URL + LOGIN_ENDPOINT
    invalid_credentials = [
        {"email": "nonexistentuser@example.com", "password": "wrongpassword"},
        {"email": "admin@parking.com", "password": "wrongpassword"},
        {"email": "invalidemailformat", "password": "somepassword"},
        {"email": "admin@parking.com", "password": ""},
        {"email": "", "password": "somepassword"},
    ]

    headers = {
        "Content-Type": "application/json"
    }

    for creds in invalid_credentials:
        try:
            response = requests.post(url, json=creds, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as e:
            assert False, f"Request failed: {e}"

        # Should be 401 Unauthorized or 400 Bad Request for invalid credentials
        assert response.status_code in (400, 401), (
            f"Expected status 400 or 401, got {response.status_code} for input {creds}"
        )
        try:
            json_resp = response.json()
        except Exception:
            assert False, "Response is not valid JSON"

        # Check error message presence
        error_msg = json_resp.get("msg") or json_resp.get("message") or json_resp.get("error")
        # The app likely returns message indicating invalid credentials or validation errors
        assert error_msg is not None, f"No error message in response for input {creds}"
        assert any(keyword in error_msg.lower() for keyword in ["invalid", "error", "credentials", "email", "password"]), (
            f"Unexpected error message: {error_msg}"
        )


test_post_login_user_with_incorrect_credentials()