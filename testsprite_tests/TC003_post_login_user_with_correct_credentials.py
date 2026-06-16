import requests

BASE_URL = "http://localhost:5000"
LOGIN_ENDPOINT = "/api/v1/auth/login"
TIMEOUT = 30

def test_post_login_user_with_correct_credentials():
    email = "admin@parking.com"
    password = "admin123"
    login_url = BASE_URL + LOGIN_ENDPOINT

    login_payload = {
        "email": email,
        "password": password
    }

    try:
        # POST to login endpoint
        login_response = requests.post(login_url, json=login_payload, timeout=TIMEOUT)
        assert login_response.status_code == 200, f"Expected 200, got {login_response.status_code}"
        login_data = login_response.json()
        assert "access_token" in login_data, "No access_token received in login response"

    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_post_login_user_with_correct_credentials()
