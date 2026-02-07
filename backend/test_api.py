#!/usr/bin/env python3
"""
Test script to verify upload functionality
"""
import requests
import json

# Test endpoints
BASE_URL = "http://localhost:8000/api"

def test_login():
    """Test login functionality"""
    print("Testing login...")
    
    login_data = {
        "username": "admin@talentai.com",
        "password": "admin123"
    }
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("✅ Login successful")
        return token
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None

def test_candidates_endpoint(token):
    """Test candidates endpoint"""
    print("Testing candidates endpoint...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/candidates", headers=headers)
    
    if response.status_code == 200:
        candidates = response.json()
        print(f"✅ Candidates endpoint working - Found {len(candidates)} candidates")
        return True
    else:
        print(f"❌ Candidates endpoint failed: {response.status_code} - {response.text}")
        return False

def test_jobs_endpoint(token):
    """Test jobs endpoint"""
    print("Testing jobs endpoint...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/jobs", headers=headers)
    
    if response.status_code == 200:
        jobs = response.json()
        print(f"✅ Jobs endpoint working - Found {len(jobs)} jobs")
        return True
    else:
        print(f"❌ Jobs endpoint failed: {response.status_code} - {response.text}")
        return False

def main():
    print("=== BACKEND API TEST ===\n")
    
    # Test login
    token = test_login()
    if not token:
        print("Cannot proceed without valid token")
        return
    
    print()
    
    # Test endpoints
    test_candidates_endpoint(token)
    test_jobs_endpoint(token)
    
    print("\n=== TEST COMPLETE ===")
    print("\nIf all tests pass, try uploading a resume from the frontend.")
    print("Make sure both backend and frontend servers are running:")
    print("Backend: uvicorn app.main:app --reload --port 8000")
    print("Frontend: npm run dev")

if __name__ == "__main__":
    main()