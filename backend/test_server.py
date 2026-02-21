import requests

try:
    response = requests.get('http://localhost:8000/api/health', timeout=5)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except requests.exceptions.ConnectionError:
    print("ERROR: Cannot connect to server - server is not running or not accessible")
except Exception as e:
    print(f"ERROR: {e}")
