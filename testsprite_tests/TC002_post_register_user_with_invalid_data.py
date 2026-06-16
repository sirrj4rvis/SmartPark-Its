import requests

BASE_URL = "http://localhost:5000"
REGISTER_ENDPOINT = "/api/v1/auth/register"
TIMEOUT = 30

def test_post_register_user_with_invalid_data():
    url = BASE_URL + REGISTER_ENDPOINT

    # Test cases for invalid registration data with expected 400 status
    invalid_test_data = [
        # Missing name
        {"email": "user@example.com", "password": "validPass123"},
        # Missing email
        {"name": "Test User", "password": "validPass123"},
        # Missing password
        {"name": "Test User", "email": "user@example.com"},
        # Password too short (<8)
        {"name": "Test User", "email": "user@example.com", "password": "short"},
        # Malformed email
        {"name": "Test User", "email": "user@.com", "password": "validPass123"},
        # Malformed email no @
        {"name": "Test User", "email": "userexample.com", "password": "validPass123"},
        # Empty strings
        {"name": "", "email": "user@example.com", "password": "validPass123"},
        {"name": "Test User", "email": "", "password": "validPass123"},
        {"name": "Test User", "email": "user@example.com", "password": ""},
    ]

    headers = {
        "Content-Type": "application/json"
    }

    for payload in invalid_test_data:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        except Exception as e:
            assert False, f"Request failed with exception: {e}"

        # Validate the response is 400 Bad Request for invalid inputs
        assert response.status_code == 400, (
            f"Expected status code 400 for payload {payload}, got {response.status_code}"
        )

        # Validate response contains validation error message
        try:
            resp_json = response.json()
        except Exception:
            assert False, "Response is not valid JSON"

        # Expect error message keys or message field in response json
        error_msg_keys = ['error', 'message', 'errors', 'validation']
        if not any(key in resp_json for key in error_msg_keys):
            assert False, f"Response JSON does not contain expected validation error keys for payload {payload}"

test_post_register_user_with_invalid_data()