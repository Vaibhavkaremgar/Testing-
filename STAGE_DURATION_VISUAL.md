# Stage Duration Tracking - Visual Guide

## 📸 What It Looks Like

### Before (Old Pipeline)
```
┌─────────────────────────┐
│ John Doe                │
│ 👔 Senior Developer     │
│ TechCorp Inc.           │
│ [Backend Engineer] ⭐ 85│
└─────────────────────────┘
```

### After (With Duration Tracking)
```
┌─────────────────────────┐
│ John Doe                │
│ 👔 Senior Developer     │
│ TechCorp Inc.           │
│ [Backend Engineer] ⭐ 85│
│ [Waiting: 3 days]       │  ← NEW: Timer badge
└─────────────────────────┘
```

### Shortlisted Stage (Special)
```
┌─────────────────────────┐
│ Jane Smith              │
│ 👔 Full Stack Developer │
│ StartupXYZ              │
│ [Frontend Dev] ⭐ 92    │
│ [Waiting: 5 days]       │  ← Days in Shortlisted
│ Total: 12 days          │  ← NEW: Applied → Shortlisted
│ (Applied → Shortlisted) │
└─────────────────────────┘
```

### Rejected Stage (Clean)
```
┌─────────────────────────┐
│ Bob Johnson             │
│ 👔 Junior Developer     │
│ CodeCo                  │
│ [Backend] ⭐ 45         │
│                         │  ← No badges (clean UI)
└─────────────────────────┘
```

## 🎨 Badge Variations

### Same Day Upload
```
[Waiting: few hours]
```

### 1 Day
```
[Waiting: 1 day]
```

### Multiple Days
```
[Waiting: 7 days]
```

### Total Days (Shortlisted Only)
```
Total: 12 days (Applied → Shortlisted)
```

## 📊 Real-World Example

### Scenario: Candidate Journey

**Day 0 (Upload)**
- Stage: APPLIED
- Badge: `[Waiting: few hours]`

**Day 2 (Screening Complete)**
- Stage: SHORTLISTED
- Badge: `[Waiting: few hours]`
- Total: `Total: 2 days (Applied → Shortlisted)`

**Day 5 (Interview Scheduled)**
- Stage: INTERVIEW_SCHEDULED
- Badge: `[Waiting: few hours]`

**Day 7 (Interview Done)**
- Stage: INTERVIEWED
- Badge: `[Waiting: few hours]`

**Day 10 (Offer Made)**
- Stage: SELECTED
- Badge: `[Waiting: few hours]`

## 🎯 Key Metrics Tracked

1. **Time in Current Stage**
   - Helps identify bottlenecks
   - Shows which candidates are waiting too long
   - Resets on every stage change

2. **Time to Shortlist** (Shortlisted stage only)
   - Critical hiring metric
   - Shows efficiency of initial screening
   - Helps optimize resume review process

## 💡 Use Cases

### For Recruiters
- "This candidate has been in Interview Scheduled for 10 days - need to follow up!"
- "We're shortlisting candidates in 2-3 days on average - great!"

### For Hiring Managers
- "Total time from application to shortlist is 5 days - within our SLA"
- "This candidate has been waiting 7 days for interview - let's prioritize"

### For Analytics
- Track average time in each stage
- Identify process bottlenecks
- Measure hiring velocity improvements

## 🔧 Technical Details

### Data Flow
```
Upload Resume
    ↓
applied_at = NOW()
stage_entered_at = NOW()
    ↓
Move to Shortlisted
    ↓
stage_entered_at = NOW()
(applied_at unchanged)
    ↓
Calculate:
- Days in stage = NOW() - stage_entered_at
- Total days = stage_entered_at - applied_at
```

### Edge Cases
- **Null timestamps**: Falls back to `applied_at`
- **Negative days**: Returns 0
- **Same day**: Shows "few hours"
- **Rejected stage**: No badges shown

## ✨ Benefits

1. **Visibility**: See at a glance how long candidates are waiting
2. **Accountability**: Track team response times
3. **Optimization**: Identify and fix bottlenecks
4. **Metrics**: Data-driven hiring process improvements
5. **Candidate Experience**: Reduce wait times, improve satisfaction

---

**This feature makes your hiring pipeline transparent and actionable!** 🚀
