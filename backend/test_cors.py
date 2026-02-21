import requests

try:
    response = requests.options('http://localhost:8000/api/health', 
                               headers={'Origin': 'http://localhost:5173'})
    print(f"Status: {response.status_code}")
    print(f"CORS Headers:")
    print(f"  Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'NOT SET')}")
    print(f"  Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'NOT SET')}")
    print(f"  Access-Control-Allow-Headers: {response.headers.get('Access-Control-Allow-Headers', 'NOT SET')}")
except Exception as e:
    print(f"ERROR: {e}")
