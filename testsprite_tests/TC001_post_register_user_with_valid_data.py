import requests
import uuid

BASE_URL = "http://localhost:5000"

def test_post_register_user_with_valid_data():
    url = f"{BASE_URL}/api/v1/auth/register"
    # Create unique email to avoid duplicate conflict
    unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "name": "Test User",
        "email": unique_email,
        "password": "strongpassword"
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"
    else:
        assert response.status_code == 201 or response.status_code == 200, \
            f"Unexpected status code: {response.status_code}, response: {response.text}"
        json_response = response.json()
        # Check within the 'user' object for email and name
        assert "user" in json_response, f"Response JSON missing 'user' object: {json_response}"
        user = json_response["user"]
        assert "email" in user and user["email"] == unique_email, \
            f"User object missing or mismatched email: {user}"
        assert "name" in user and user["name"] == "Test User", \
            f"User object missing or mismatched name: {user}"

test_post_register_user_with_valid_data()
