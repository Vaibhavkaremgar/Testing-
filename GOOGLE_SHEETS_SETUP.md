# Google Sheets Integration Setup Guide

## Overview
This guide will help you set up Google Sheets integration for syncing candidate data.

## Prerequisites
- Google Account
- Access to Google Cloud Console

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it "HR Dashboard" or similar
4. Click "Create"

### 2. Enable Google Sheets API

1. In your project, go to "APIs & Services" → "Library"
2. Search for "Google Sheets API"
3. Click on it and press "Enable"

### 3. Create Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Fill in details:
   - **Service account name**: `hr-dashboard-service`
   - **Service account ID**: (auto-generated)
   - **Description**: "Service account for HR Dashboard Google Sheets sync"
4. Click "Create and Continue"
5. Skip "Grant this service account access to project" (click Continue)
6. Skip "Grant users access to this service account" (click Done)

### 4. Create and Download Key

1. In the Credentials page, find your service account
2. Click on the service account email
3. Go to "Keys" tab
4. Click "Add Key" → "Create new key"
5. Choose "JSON" format
6. Click "Create"
7. The key file will download automatically (e.g., `hr-dashboard-xxxxx.json`)

### 5. Rename and Place the Key File

**For Local Development:**
1. Rename the downloaded file to `hr-dashboard-key.json`
2. Place it in the `backend` directory:
   ```
   ai-recruitment-dashboard/
   └── backend/
       ├── app/
       ├── hr-dashboard-key.json  ← Place here
       └── requirements.txt
   ```

**For Production (Railway/Heroku):**
1. Open the JSON file in a text editor
2. Copy the entire JSON content
3. In your hosting platform (Railway/Heroku):
   - Go to Environment Variables
   - Add new variable:
     - **Name**: `GOOGLE_SHEETS_CREDENTIALS`
     - **Value**: Paste the entire JSON content
4. Restart your application

### 6. Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Name it "HR Dashboard - Candidates"
4. Copy the Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit
   ```

### 7. Share Sheet with Service Account

1. In your Google Sheet, click "Share" button
2. Paste the service account email (from step 3):
   - Format: `hr-dashboard-service@your-project.iam.gserviceaccount.com`
3. Give it "Editor" access
4. Uncheck "Notify people"
5. Click "Share"

### 8. Update Sheet ID in Code

1. Open `backend/app/google_sheets.py`
2. Find line 10:
   ```python
   self.sheet_id = "18ugwqo2-_A80zPP_JfCRL6sDKNGBCweWkxsFuSmfQmE"
   ```
3. Replace with your Sheet ID from step 6

### 9. Restart Backend

```bash
cd backend
# If using virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Restart the server
uvicorn app.main:app --reload --port 8000
```

### 10. Test the Integration

1. Go to your dashboard
2. Navigate to "Resumes" page
3. Click "Sync to Sheets" button
4. Check your Google Sheet - candidate data should appear!

## Troubleshooting

### Error: "Google Sheets service not configured"
- **Cause**: Key file not found or environment variable not set
- **Solution**: 
  - Local: Ensure `hr-dashboard-key.json` is in `backend/` directory
  - Production: Verify `GOOGLE_SHEETS_CREDENTIALS` environment variable is set

### Error: "Permission denied"
- **Cause**: Sheet not shared with service account
- **Solution**: Share the sheet with service account email (step 7)

### Error: "Invalid credentials"
- **Cause**: Corrupted or incorrect JSON key
- **Solution**: Download a new key from Google Cloud Console

### Error: "API not enabled"
- **Cause**: Google Sheets API not enabled
- **Solution**: Enable it in Google Cloud Console (step 2)

## Security Notes

⚠️ **IMPORTANT**: 
- Never commit `hr-dashboard-key.json` to Git
- The file is already in `.gitignore`
- For production, always use environment variables
- Rotate keys periodically for security

## What Gets Synced?

**To Google Sheets (Sync to Sheets):**
- Candidate ID
- Name
- Email
- Phone
- Job ID & Title
- Resume Text (truncated to 2000 chars)
- Job Description (truncated to 1000 chars)
- Empty columns for: Score, Skills, Resume_Evaluated, Summary

**From Google Sheets (Sync from Sheets):**
- Updated scores
- Updated skills
- AI-generated summaries
- Stage changes based on email communications

## Sheet Structure

Your Google Sheet will have these columns:
```
| Candidate_ID | CandidateName | Email | Phone | Job_ID | Job_Title | Resume_Text | Job_Description | Score | Skills | Resume_Evaluated | Summary |
```

## Need Help?

If you encounter issues:
1. Check backend logs for detailed error messages
2. Verify all steps above are completed
3. Ensure Google Sheets API is enabled
4. Confirm service account has Editor access to the sheet
