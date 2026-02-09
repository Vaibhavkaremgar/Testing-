import os
import json

# Test if environment variable is set
google_creds = os.getenv('GOOGLE_SHEETS_CREDENTIALS')

if google_creds:
    print("✅ GOOGLE_SHEETS_CREDENTIALS environment variable is SET")
    print(f"Length: {len(google_creds)} characters")
    try:
        creds_dict = json.loads(google_creds)
        print(f"✅ JSON is valid")
        print(f"Project ID: {creds_dict.get('project_id', 'N/A')}")
        print(f"Client Email: {creds_dict.get('client_email', 'N/A')}")
    except Exception as e:
        print(f"❌ JSON parsing failed: {e}")
else:
    print("❌ GOOGLE_SHEETS_CREDENTIALS environment variable is NOT SET")

print("\nAll environment variables:")
for key in os.environ:
    if 'GOOGLE' in key.upper():
        print(f"  {key}: {'SET' if os.environ[key] else 'EMPTY'}")
