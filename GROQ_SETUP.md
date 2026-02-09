# FREE AI Resume Scoring with Groq

Get intelligent resume analysis with **ZERO cost** using Groq's free API.

## Why Groq?

- ✅ **100% FREE** - No credit card required
- ✅ **Fast** - 0.5-1 second per resume
- ✅ **Accurate** - Uses Llama 3.1 70B model
- ✅ **High Limits** - 30 requests/minute, 14,400/day
- ✅ **Easy Setup** - 2 minutes to get started

## Setup Steps

### 1. Get Your Free Groq API Key

1. Go to https://console.groq.com
2. Sign up with Google/GitHub (takes 30 seconds)
3. Click "API Keys" in the left sidebar
4. Click "Create API Key"
5. Copy your API key (starts with `gsk_...`)

### 2. Add API Key to Your Backend

Open `backend/.env` and update:

```env
# LLM Configuration
GROQ_API_KEY=gsk_your_actual_api_key_here
LLM_PROVIDER=groq
```

### 3. Restart Backend

```bash
cd backend
# Stop the server (Ctrl+C)
# Start again
uvicorn app.main:app --reload --port 8000
```

### 4. Test It!

Upload a resume and watch the console output:

```
AI ANALYSIS RESULT
==================================================
Match Score: 78.5
Status: shortlisted
Summary: Experienced professional with 5+ years...
==================================================
```

## What You Get

### With Groq (FREE):
- ✅ Unique scores for each resume (25-95 range)
- ✅ AI-generated professional summaries
- ✅ Context-aware evaluation
- ✅ Skill gap analysis
- ✅ Intelligent recommendations

### Without Groq (Fallback):
- ⚠️ Rule-based scoring (less accurate)
- ⚠️ Generic summaries
- ⚠️ Basic keyword matching

## Performance

- **Single Resume**: ~0.5-1 second
- **100 Resumes**: ~1-2 minutes
- **500 Resumes**: ~5-8 minutes

## Troubleshooting

### "LLM evaluation failed"
- Check your API key is correct
- Verify `LLM_PROVIDER=groq` in `.env`
- Restart backend server

### "Rate limit exceeded"
- Groq free tier: 30 requests/minute
- Wait 1 minute and try again
- Or upgrade to Groq Pro (still very cheap)

### Still getting same scores?
- Make sure backend restarted after adding API key
- Check console logs for "AI ANALYSIS RESULT"
- Verify `.env` file is in `backend/` folder

## Alternative: OpenAI (Paid)

If you prefer OpenAI:

```env
OPENAI_API_KEY=sk-your-openai-key
LLM_PROVIDER=openai
```

Note: OpenAI costs ~$0.002 per resume (500 resumes = $1)

## Need Help?

Check the console output when uploading resumes. You'll see:
- ✓ "AI ANALYSIS RESULT" = Groq is working
- ⚠ "No AI analysis" = Fallback mode (add API key)
