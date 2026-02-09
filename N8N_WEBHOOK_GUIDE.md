# N8N Workflow Integration Guide

## Webhook Endpoint for Communications

### Production Endpoint
```
POST https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email
```

Replace `YOUR-BACKEND-URL` with your actual Railway backend URL.

---

## N8N Workflow Setup

### Step 1: After LLM Shortlists/Rejects Resume

In your N8N workflow, after the LLM makes a decision:

**HTTP Request Node Configuration:**

**Method:** `POST`

**URL:** 
```
https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email
```

**Authentication:** None (or add Bearer token if you want to secure it)

**Headers:**
```json
{
  "Content-Type": "application/json"
}
```

**Body (JSON):**
```json
{
  "candidate_id": "{{ $json.candidate_id }}",
  "email_type": "{{ $json.decision === 'shortlisted' ? 'interview_invitation' : 'rejection' }}",
  "status": "sent"
}
```

---

## Request Body Fields

### Required Fields:

**candidate_id** (string)
- The candidate's ID from your system
- Example: `"ABC123"`, `"JOH001"`

**email_type** (string)
- Options: `"offer_letter"`, `"rejection"`, `"interview_invitation"`
- Use based on LLM decision

**status** (string)
- Options: `"sent"`, `"failed"`
- Use `"sent"` if email was sent successfully
- Use `"failed"` if email sending failed

---

## Example Requests

### Shortlisted Candidate (Interview Invitation)
```bash
curl -X POST https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_id": "JOH001",
    "email_type": "interview_invitation",
    "status": "sent"
  }'
```

### Rejected Candidate
```bash
curl -X POST https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_id": "JOH001",
    "email_type": "rejection",
    "status": "sent"
  }'
```

### Offer Letter
```bash
curl -X POST https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_id": "JOH001",
    "email_type": "offer_letter",
    "status": "sent"
  }'
```

---

## Response Format

### Success Response (200 OK)
```json
{
  "success": true,
  "candidate_id": "JOH001",
  "email_type": "rejection",
  "status": "sent"
}
```

### Error Response (404 Not Found)
```json
{
  "detail": "Candidate not found"
}
```

---

## N8N Workflow Example

```
1. Trigger (Webhook/Schedule)
   ↓
2. Get Candidates from Database/Sheets
   ↓
3. LLM Node (Analyze Resume vs JD)
   ↓
4. IF Node (Check LLM Decision)
   ├─ Shortlisted → Send Interview Email
   │                 ↓
   │                 HTTP Request (log-email with type: interview_invitation)
   │
   └─ Rejected → Send Rejection Email
                  ↓
                  HTTP Request (log-email with type: rejection)
```

---

## View Communications in Dashboard

After N8N sends the webhook:
1. Go to your dashboard
2. Click "Communications" tab
3. You'll see all logged emails with:
   - Candidate name
   - Email address
   - Email type (Interview Invitation, Rejection, Offer Letter)
   - Status (Sent, Failed)
   - Date sent

---

## Additional Endpoints

### Get All Communications (for N8N to read)
```
GET https://YOUR-BACKEND-URL.up.railway.app/api/webhook/communications
```

Returns list of all email communications.

### Update Candidate Score (optional)
```
POST https://YOUR-BACKEND-URL.up.railway.app/api/webhook/update-score
```

Body:
```json
{
  "candidate_id": "JOH001",
  "score": 85.5
}
```

This will also auto-update the candidate's stage based on the score.

---

## Testing

### Test with Postman/Insomnia:

1. **Method:** POST
2. **URL:** `https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email`
3. **Headers:** `Content-Type: application/json`
4. **Body:**
```json
{
  "candidate_id": "TEST001",
  "email_type": "rejection",
  "status": "sent"
}
```

5. Check Communications tab in dashboard to see the logged email

---

## Security (Optional)

To secure the webhook, you can add authentication:

1. Add a secret token in Railway backend environment variables:
```
WEBHOOK_SECRET=your-secret-token-here
```

2. In N8N, add header:
```
Authorization: Bearer your-secret-token-here
```

3. Update the webhook endpoint to validate the token (I can help with this if needed)

---

## Your Production URLs

**Backend API Base:** `https://YOUR-BACKEND-URL.up.railway.app`

**Webhook Endpoint:** `https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email`

**Communications View:** `https://YOUR-BACKEND-URL.up.railway.app/api/webhook/communications`

---

## Quick Start for N8N

1. In N8N, add "HTTP Request" node after your email sending step
2. Set URL to: `https://YOUR-BACKEND-URL.up.railway.app/api/webhook/log-email`
3. Set Method to: `POST`
4. Set Body to:
```json
{
  "candidate_id": "{{ $json.candidate_id }}",
  "email_type": "{{ $json.email_type }}",
  "status": "sent"
}
```
5. Done! Emails will appear in Communications tab

---

**The endpoint is already deployed and working!** Just use it in your N8N workflow.
