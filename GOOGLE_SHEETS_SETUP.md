# Google Sheets Integration Setup

## Problem
"Sync failed: Google Sheets service not configured. Please add hr-dashboard-key.json file and restart the application."

## Solution

The app now supports **two methods** for Google Sheets authentication:

### Method 1: Environment Variable (Recommended for Railway)

**Step 1**: Get your Google Service Account JSON key
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create/select a project
- Enable Google Sheets API
- Create a Service Account
- Download the JSON key file

**Step 2**: Copy the entire JSON content

**Step 3**: In Railway Backend Service, add environment variable:
```
Variable Name: GOOGLE_SHEETS_CREDENTIALS
Value: {paste entire JSON content here}
```

Example JSON format:
```json
{
  "type": "service_account",
  "project_id": "your-project",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

**Step 4**: Share your Google Sheet with the service account email
- Open your Google Sheet
- Click "Share"
- Add the `client_email` from the JSON (e.g., `your-service-account@your-project.iam.gserviceaccount.com`)
- Give it "Editor" permissions

**Step 5**: Restart Railway backend service

### Method 2: JSON File (For Local Development)

**Step 1**: Download your service account JSON key

**Step 2**: Place it in the backend directory:
```
backend/hr-dashboard-key.json
```

**Step 3**: Share your Google Sheet with the service account email

**Step 4**: Restart the backend:
```bash
cd backend
uvicorn app.main:app --reload
```

## Verify Setup

After setup, check backend logs for:
```
✓ Google Sheets service initialized successfully from environment
```
or
```
✓ Google Sheets service initialized successfully from file
```

## Current Sheet ID

The app is configured to use this Google Sheet:
```
Sheet ID: 18ugwqo2-_A80zPP_JfCRL6sDKNGBCweWkxsFuSmfQmE
```

To change it, update `backend/app/google_sheets.py` line 10.

## Troubleshooting

**Error: "Google Sheets service not configured"**
- Check if `GOOGLE_SHEETS_CREDENTIALS` environment variable is set in Railway
- Verify JSON format is valid
- Restart the backend service

**Error: "Permission denied"**
- Make sure you shared the Google Sheet with the service account email
- Give "Editor" permissions, not just "Viewer"

**Error: "Invalid credentials"**
- Verify the JSON content is complete and not truncated
- Check that Google Sheets API is enabled in your Google Cloud project

## Security Note

⚠️ **Never commit the JSON key file to git!**
- The file is already in `.gitignore`
- Always use environment variables for production
