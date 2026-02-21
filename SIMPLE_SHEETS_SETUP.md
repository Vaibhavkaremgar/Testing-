# Simple Google Sheets Integration (No Service Account Needed!)

## 5-Minute Setup - No JSON Files Required

### Step 1: Create Your Google Sheet

1. Go to https://sheets.google.com
2. Create a new spreadsheet
3. Name it "HR Dashboard - Candidates"
4. Add these column headers in Row 1:
   ```
   Candidate_ID | CandidateName | Email | Phone | Job_ID | Job_Title | Resume_Text | Job_Description | Score | Skills | Resume_Evaluated | Summary
   ```

### Step 2: Create Apps Script Webhook

1. In your Google Sheet, click **Extensions** → **Apps Script**
2. Delete any existing code
3. Paste this code:

```javascript
function doPost(e) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const data = JSON.parse(e.postData.contents);
    
    // Get existing candidate IDs
    const existingData = sheet.getDataRange().getValues();
    const existingIds = new Set();
    for (let i = 1; i < existingData.length; i++) {
      if (existingData[i][0]) {
        existingIds.add(existingData[i][0]);
      }
    }
    
    let newCount = 0;
    
    // Add only new candidates
    data.candidates.forEach(candidate => {
      if (!existingIds.has(candidate.candidate_id)) {
        sheet.appendRow([
          candidate.candidate_id,
          candidate.name,
          candidate.email,
          candidate.phone || '',
          candidate.job_id || '',
          candidate.job_title || '',
          candidate.resume_text || '',
          candidate.job_description || '',
          candidate.score || '',
          candidate.skills || '',
          '',  // Resume_Evaluated
          ''   // Summary
        ]);
        newCount++;
      }
    });
    
    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      synced_count: newCount
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
```

4. Click **Deploy** → **New deployment**
5. Click gear icon ⚙️ → Select **Web app**
6. Settings:
   - **Execute as**: Me
   - **Who has access**: Anyone
7. Click **Deploy**
8. **Copy the Web App URL** (looks like: `https://script.google.com/macros/s/ABC123.../exec`)

### Step 3: Update Backend Code

Open `backend/app/routes/candidates.py` and find the `sync_candidates_to_sheets` function.

Replace the Google Sheets sync section with this simple webhook call:

```python
@router.post("/sync-to-sheets")
async def sync_candidates_to_sheets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Sync candidates to Google Sheets via webhook"""
    import requests
    import os
    
    # Get webhook URL from environment variable
    webhook_url = os.getenv('GOOGLE_SHEETS_WEBHOOK_URL')
    
    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Google Sheets webhook URL not configured. Add GOOGLE_SHEETS_WEBHOOK_URL to .env file"
        )
    
    try:
        # Get all candidates
        candidates = db.query(Candidate).filter(Candidate.stage != CandidateStage.APPLIED).all()
        
        # Prepare data
        candidates_data = []
        for c in candidates:
            # Get job details
            job_title = ''
            job_description = ''
            if c.job_id:
                job = db.query(JobDescription).filter(JobDescription.id == c.job_id).first()
                if job:
                    job_title = job.title
                    job_description = job.description[:1000] if job.description else ''
            
            candidates_data.append({
                'candidate_id': c.candidate_id or f'CAND-{c.id}',
                'name': c.name,
                'email': c.email,
                'phone': c.phone or '',
                'job_id': c.job_id or '',
                'job_title': job_title,
                'resume_text': (c.resume_text[:2000] if c.resume_text else ''),
                'job_description': job_description,
                'score': c.resume_score or '',
                'skills': ', '.join(c.skills) if c.skills else ''
            })
        
        # Send to Google Sheets
        response = requests.post(
            webhook_url,
            json={'candidates': candidates_data},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'sheets_synced': result.get('synced_count', len(candidates_data)),
                'message': f'Successfully synced {result.get("synced_count", 0)} new candidates to Google Sheets'
            }
        else:
            raise HTTPException(status_code=500, detail=f'Webhook failed: {response.text}')
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Sync failed: {str(e)}')
```

### Step 4: Add Webhook URL to Environment

1. Open `backend/.env` file (create if doesn't exist)
2. Add this line with YOUR webhook URL:
   ```
   GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec
   ```

### Step 5: Restart Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### Step 6: Test It!

1. Upload some resumes in your dashboard
2. Click "Sync to Sheets" button
3. Check your Google Sheet - data should appear! ✅

---

## How It Works

1. **Upload Resume** → Backend extracts data (Name, Email, Phone, Skills, etc.)
2. **Click "Sync to Sheets"** → Backend sends data to Google Apps Script webhook
3. **Apps Script** → Adds new rows to your Google Sheet
4. **Done!** → All candidate data is now in Google Sheets

## Advantages

✅ No service account needed  
✅ No JSON key files  
✅ No Google Cloud Console setup  
✅ Works immediately  
✅ Free forever  
✅ Easy to modify  

## Troubleshooting

**Error: "Webhook URL not configured"**
- Add `GOOGLE_SHEETS_WEBHOOK_URL` to `backend/.env` file

**Error: "Authorization required"**
- In Apps Script, redeploy with "Who has access: Anyone"

**Data not appearing**
- Check Apps Script logs: View → Executions
- Verify column headers match exactly

## What Gets Synced

From your uploaded resumes:
- ✅ Candidate_ID (auto-generated)
- ✅ CandidateName (extracted from resume)
- ✅ Email (extracted from resume)
- ✅ Phone (extracted from resume)
- ✅ Job_ID (from selected job)
- ✅ Job_Title (from selected job)
- ✅ Resume_Text (full text, truncated to 2000 chars)
- ✅ Job_Description (from job, truncated to 1000 chars)
- ✅ Score (AI-generated resume score)
- ✅ Skills (extracted skills, comma-separated)
- ⬜ Resume_Evaluated (empty - for your use)
- ⬜ Summary (empty - for your use)

---

**That's it! No complex setup, no service accounts, just works!** 🎉
