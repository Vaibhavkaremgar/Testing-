"""
Test new analytics endpoints
"""
import requests

BASE_URL = "http://localhost:8000/api"

# You'll need to login first to get a token
def test_endpoints():
    # Login
    login_data = {
        "username": "recruiter@talentai.com",
        "password": "recruiter123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test endpoints
    endpoints = [
        "/analytics/dashboard-stats",
        "/analytics/source-breakdown",
        "/analytics/decline-reasons",
        "/analytics/offer-acceptance-rate",
        "/analytics/active-jobs",
        "/analytics/upcoming-interviews"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            print(f"\n{endpoint}: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  Data: {data if len(str(data)) < 200 else str(data)[:200] + '...'}")
            else:
                print(f"  Error: {response.text}")
        except Exception as e:
            print(f"  Exception: {e}")

if __name__ == "__main__":
    test_endpoints()
