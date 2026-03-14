# API Polling Issue - FOUND & FIX

## Problem Identified

In **`frontend/src/pages/Resumes.jsx`** (lines 73-79), there's a polling mechanism that calls the `/jobs` API every 5 seconds:

```javascript
useEffect(() => {
  const fetchJobScores = async () => {
    try {
      const jobsData = await api.getJobs()  // ← Called every 5 seconds!
      const scores = {}
      jobsData.forEach(job => {
        scores[job.id] = job.min_passing_score || 60
      })
      setJobScores(scores)
    } catch (error) {
      console.error('Failed to fetch job scores:', error)
    }
  }
  fetchJobScores()
  
  // Refresh job scores every 5 seconds to catch updates
  const interval = setInterval(fetchJobScores, 5000)  // ← POLLING!
  return () => clearInterval(interval)
}, [])
```

## Why This Exists

The polling was added to keep job scores (min_passing_score) updated in real-time when admins change them. However, this is causing:

1. **Excessive API calls** - 8+ calls in network tab
2. **Unnecessary server load**
3. **Wasted bandwidth**
4. **Poor performance**

## Solutions

### Option 1: Remove Polling (Recommended)
Remove the interval and only fetch once on mount. Users can refresh the page if they need updated scores.

### Option 2: Increase Interval
Change from 5 seconds to 30-60 seconds to reduce load.

### Option 3: Event-Based Updates
Use WebSockets or Server-Sent Events for real-time updates (more complex).

### Option 4: Fetch on Demand
Only fetch job scores when the upload modal is opened.

## Recommended Fix

**Remove the polling interval** since job scores don't change frequently enough to warrant polling every 5 seconds.

### File to Modify:
`frontend/src/pages/Resumes.jsx`

### Change:
```javascript
// BEFORE (lines 63-79):
useEffect(() => {
  const fetchJobScores = async () => {
    try {
      const jobsData = await api.getJobs()
      const scores = {}
      jobsData.forEach(job => {
        scores[job.id] = job.min_passing_score || 60
      })
      setJobScores(scores)
    } catch (error) {
      console.error('Failed to fetch job scores:', error)
    }
  }
  fetchJobScores()
  
  // Refresh job scores every 5 seconds to catch updates
  const interval = setInterval(fetchJobScores, 5000)  // ← REMOVE THIS
  return () => clearInterval(interval)  // ← REMOVE THIS
}, [])

// AFTER:
useEffect(() => {
  const fetchJobScores = async () => {
    try {
      const jobsData = await api.getJobs()
      const scores = {}
      jobsData.forEach(job => {
        scores[job.id] = job.min_passing_score || 60
      })
      setJobScores(scores)
    } catch (error) {
      console.error('Failed to fetch job scores:', error)
    }
  }
  fetchJobScores()
  // Removed polling - fetch only once on mount
}, [])
```

## Alternative: Fetch on Upload Modal Open

If you want fresh scores when uploading, fetch them when the upload section is used:

```javascript
// Add to the upload handler
const handleUpload = async (files) => {
  // Fetch latest job scores before upload
  const jobsData = await api.getJobs()
  const scores = {}
  jobsData.forEach(job => {
    scores[job.id] = job.min_passing_score || 60
  })
  setJobScores(scores)
  
  // ... rest of upload logic
}
```

## Impact After Fix

- ✅ Reduces API calls from 8+ to 1-2 per page load
- ✅ Improves performance
- ✅ Reduces server load
- ✅ Better user experience
- ⚠️ Job scores won't auto-update (user needs to refresh page)

## Other Pages to Check

Make sure no other pages have similar polling:
- ✅ Jobs.jsx - No polling found
- ✅ Clients.jsx - No polling found
- ✅ Interviews.jsx - No polling found
- ⚠️ Resumes.jsx - **POLLING FOUND** (needs fix)

## Testing After Fix

1. Open Resumes page
2. Open browser DevTools → Network tab
3. Filter by "jobs"
4. Should see only 1-2 calls on initial load
5. Wait 30 seconds - should see NO additional calls
