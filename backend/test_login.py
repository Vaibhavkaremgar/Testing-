import requests

# First, ensure user exists
print("Creating/Resetting admin user...")

register_data = {
    "email": "admin@example.com",
    "password": "admin123",
    "full_name": "Admin User",
    "role": "admin"
}

try:
    response = requests.post("http://localhost:8000/api/auth/register", json=register_data)
    if response.status_code == 200:
        print("✅ User created successfully!")
    elif response.status_code == 400:
        print("ℹ️  User already exists (this is OK)")
    else:
        print(f"⚠️  Register response: {response.status_code}")
except Exception as e:
    print(f"Register error: {e}")

# Now test login
print("\nTesting login...")

login_data = {
    "username": "admin@example.com",  # OAuth2 uses 'username' field
    "password": "admin123"
}

try:
    response = requests.post(
        "http://localhost:8000/api/auth/login",
        data=login_data,  # Use 'data' not 'json' for form data
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ LOGIN SUCCESS!")
        token = response.json()["access_token"]
        print(f"Token: {token[:50]}...")
    else:
        print(f"❌ LOGIN FAILED!")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"Login error: {e}")

print("\n" + "="*60)
print("Use these credentials in the frontend:")
print("Email: admin@example.com")
print("Password: admin123")
print("="*60)
