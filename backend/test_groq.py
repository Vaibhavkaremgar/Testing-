"""
Test Groq API Integration
Run this to verify your Groq API key is working
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if not GROQ_API_KEY:
    print("❌ ERROR: GROQ_API_KEY not found in .env file")
    print("\n📝 Steps to fix:")
    print("1. Go to https://console.groq.com")
    print("2. Create an account (free)")
    print("3. Get your API key")
    print("4. Add to backend/.env: GROQ_API_KEY=gsk_your_key_here")
    exit(1)

print(f"🔑 Testing Groq API key: {GROQ_API_KEY[:20]}...")

# Test API call
try:
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.1-70b-versatile",
            "messages": [{"role": "user", "content": "Say 'Hello from Groq!' if you're working."}],
            "temperature": 0.3,
            "max_tokens": 50
        },
        timeout=10
    )
    
    if response.status_code == 200:
        result = response.json()
        message = result["choices"][0]["message"]["content"]
        print(f"\n✅ SUCCESS! Groq API is working!")
        print(f"📨 Response: {message}")
        print(f"\n🎉 You're ready to use FREE AI resume scoring!")
        print(f"💡 Upload resumes and watch the AI analyze them in real-time")
    else:
        print(f"\n❌ ERROR: API returned status {response.status_code}")
        print(f"Response: {response.text}")
        print(f"\n🔧 Check your API key at https://console.groq.com")
        
except requests.exceptions.Timeout:
    print("\n❌ ERROR: Request timed out")
    print("🔧 Check your internet connection")
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    print(f"🔧 Make sure your API key is correct")
