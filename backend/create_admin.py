import requests
import json

# Register admin user
url = "http://localhost:8000/api/auth/register"
data = {
    "email": "admin@talentai.com",
    "password": "Admin@123",
    "full_name": "Admin User",
    "role": "admin"
}

try:
    response = requests.post(url, json=data)
    if response.status_code == 200:
        print("✅ Admin user created successfully!")
        print("\n📧 Login Credentials:")
        print("   Email: admin@talentai.com")
        print("   Password: Admin@123")
        print("\n🌐 Login at: http://localhost:5173")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"❌ Failed to create user: {e}")
    print("\n⚠️  Make sure the backend is running at http://localhost:8000")
