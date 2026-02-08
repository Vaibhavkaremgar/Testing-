# Google Sheets Integration Setup

## Current Status: ❌ Not Configured

The Google Sheets sync functionality requires a service account key file that is currently missing.

## Setup Steps:

### 1. Create Google Cloud Service Account
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Sheets API
4. Go to "IAM & Admin" > "Service Accounts"
5. Click "Create Service Account"
6. Name it "hr-dashboard-sync" 
7. Click "Create and Continue"
8. Skip role assignment (click "Continue")
9. Click "Done"

### 2. Generate Service Account Key
1. Click on the created service account
2. Go to "Keys" tab
3. Click "Add Key" > "Create New Key"
4. Select "JSON" format
5. Download the key file
6. Rename it to `hr-dashboard-key.json`
7. Place it in the `backend/` directory

### 3. Share Google Sheet
1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/18ugwqo2-_A80zPP_JfCRL6sDKNGBCweWkxsFuSmfQmE
2. Click "Share" button
3. Add the service account email (found in the JSON key file)
4. Give "Editor" permissions
5. Click "Send"

### 4. Restart Application
After placing the key file, restart the backend service for changes to take effect.

## Testing Sync
Once configured, you can test the sync functionality:
- **Sync to Sheets**: Exports candidates to Google Sheets
- **Sync from Sheets**: Imports updates from Google Sheets

## Troubleshooting
- Ensure the JSON key file is named exactly `hr-dashboard-key.json`
- Verify the service account email has access to the Google Sheet
- Check backend logs for detailed error messages