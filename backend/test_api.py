import requests

# Test if backend is running
try:
    response = requests.get("http://localhost:8000/api/health")
    print("Backend is running")
    print(f"Response: {response.json()}")
except:
    print("Backend is NOT running!")
    print("\nStart backend with:")
    print("cd backend")
    print("uvicorn app.main:app --reload --port 8000")
    exit()

# Test dashboard stats API
try:
    # You need to login first to get token
    login_response = requests.post(
        "http://localhost:8000/api/auth/login",
        data={"username": "admin@talentai.com", "password": "admin123"}
    )
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        
        # Get dashboard stats
        stats_response = requests.get(
            "http://localhost:8000/api/analytics/dashboard-stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print("\n" + "="*50)
        print("DASHBOARD STATS FROM API")
        print("="*50)
        print(stats_response.json())
        print("="*50)
    else:
        print(f"Login failed: {login_response.status_code}")
        print("Make sure backend is initialized with users")
        
except Exception as e:
    print(f"Error: {e}")
