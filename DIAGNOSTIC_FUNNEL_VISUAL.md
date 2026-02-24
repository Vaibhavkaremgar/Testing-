# Diagnostic Funnel - Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER OPENS DASHBOARD                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND: Dashboard.jsx                                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ useEffect(() => {                                                   │ │
│  │   const diagnostic = await api.getDiagnosticFunnel()               │ │
│  │   setDiagnosticFunnel(diagnostic)                                  │ │
│  │ })                                                                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  API CLIENT: api.js                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ async getDiagnosticFunnel() {                                      │ │
│  │   return this.request('/analytics/diagnostic-funnel')             │ │
│  │ }                                                                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  BACKEND: diagnostic_funnel.py                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ @router.get("/diagnostic-funnel")                                  │ │
│  │ def get_diagnostic_funnel():                                       │ │
│  │                                                                     │ │
│  │   1. Query Database                                                │ │
│  │      ├─ Count: Applied = 150                                       │ │
│  │      ├─ Count: Screening = 85                                      │ │
│  │      ├─ Count: Interview = 45                                      │ │
│  │      └─ Count: Selected = 12                                       │ │
│  │                                                                     │ │
│  │   2. Calculate Drop-offs                                           │ │
│  │      ├─ Applied → Screening: 65 dropped (43.3%)                   │ │
│  │      ├─ Screening → Interview: 40 dropped (47.1%)                 │ │
│  │      └─ Interview → Selected: 33 dropped (73.3%) ⚠️ ABNORMAL     │ │
│  │                                                                     │ │
│  │   3. Generate AI Reasons                                           │ │
│  │      └─ Call Groq API for each drop-off                           │ │
│  │                                                                     │ │
│  │   4. Return JSON Response                                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  GROQ AI (Optional)                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Prompt: "Analyze drop-off: Interview → Selected (73.3%)"          │ │
│  │                                                                     │ │
│  │ AI Response: "Performance below expectations or high competition"  │ │
│  │                                                                     │ │
│  │ Fallback: "Performance below expectations" (if API fails)          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND: DiagnosticFunnel.jsx                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │ Applied                    [████████████████████] 150 (100%)  │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │       ↓ 65 dropped (43.3%) 📉 [Why?]                              │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │ Screening                  [███████████] 85 (56.7%)           │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │       ↓ 40 dropped (47.1%) 📉 [Why?]                              │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │ Interview                  [██████] 45 (30.0%)                │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │       ↓ 33 dropped (73.3%) 🔴 ⚠️ ABNORMAL [Why?]                 │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │ Selected                   [██] 12 (8.0%)                     │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                          User clicks [Why?]
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  SIDE PANEL MODAL                                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Drop-off Analysis                                          [X]    │ │
│  │  ─────────────────────────────────────────────────────────────────│ │
│  │                                                                     │ │
│  │  Stage Transition                                                  │ │
│  │  Interview → Selected                                              │ │
│  │                                                                     │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                       │ │
│  │  │ Dropped          │  │ Drop-off Rate    │                       │ │
│  │  │ 33               │  │ 73.3%            │                       │ │
│  │  └──────────────────┘  └──────────────────┘                       │ │
│  │                                                                     │ │
│  │  Conversion Rate                                                   │ │
│  │  [████████░░░░░░░░░░] 26.7%                                       │ │
│  │                                                                     │ │
│  │  ┌────────────────────────────────────────────────────────────┐   │ │
│  │  │ ⚠️ Abnormal Drop-off Detected                              │   │ │
│  │  │ This drop-off rate exceeds 60%, indicating a potential     │   │ │
│  │  │ issue in your hiring process.                              │   │ │
│  │  └────────────────────────────────────────────────────────────┘   │ │
│  │                                                                     │ │
│  │  ┌────────────────────────────────────────────────────────────┐   │ │
│  │  │ 💡 AI Insight                                              │   │ │
│  │  │ Performance below expectations or high competition         │   │ │
│  │  └────────────────────────────────────────────────────────────┘   │ │
│  │                                                                     │ │
│  │  Recommendations:                                                  │ │
│  │  • Review screening criteria - may be too strict                  │ │
│  │  • Check response times - delays lose candidates                  │ │
│  │  • Analyze competitor offers in market                            │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Summary

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Database │ --> │ Backend  │ --> │   API    │ --> │ Frontend │
│          │     │ Analysis │     │ Response │     │  Render  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                  │                │
     │                │                  │                │
  Candidate       Calculate          JSON with        Visual
   Counts         Drop-offs          Insights         Funnel
                     +                   +               +
                 AI Reasons          Abnormal         Modal
                                     Flags           Details
```

---

## Component Hierarchy

```
Dashboard.jsx
  │
  ├─ Card (Diagnostic Hiring Funnel)
  │   │
  │   └─ DiagnosticFunnel.jsx
  │       │
  │       ├─ Stage Bars (map over stages)
  │       │   ├─ Bar with count/percentage
  │       │   └─ Drop-off indicator
  │       │       ├─ Icon (TrendingDown)
  │       │       ├─ Text (dropped count/rate)
  │       │       ├─ Badge (if abnormal)
  │       │       └─ Button ("Why?")
  │       │
  │       ├─ Summary Stats
  │       │   ├─ Total Candidates
  │       │   ├─ Rejected
  │       │   └─ Selected
  │       │
  │       └─ Side Panel Modal (conditional)
  │           ├─ Header
  │           ├─ Metrics Cards
  │           ├─ Conversion Bar
  │           ├─ Abnormal Alert (if applicable)
  │           ├─ AI Insight Card
  │           └─ Recommendations List
```

---

## State Management

```javascript
// Dashboard.jsx
const [diagnosticFunnel, setDiagnosticFunnel] = useState(null)
  │
  └─ Passed as prop to DiagnosticFunnel
      │
      └─ DiagnosticFunnel.jsx
          const [selectedDropoff, setSelectedDropoff] = useState(null)
            │
            ├─ null: No modal shown
            └─ dropoff object: Modal shown with details
```

---

## Color Coding Logic

```
Stage Colors (Sequential):
  Applied    → Blue    (#3b82f6)
  Screening  → Purple  (#8b5cf6)
  Interview  → Orange  (#f59e0b)
  Selected   → Green   (#10b981)

Drop-off Colors (Severity):
  Normal (<60%)   → Yellow  (#f59e0b)
  Abnormal (>60%) → Red     (#ef4444)

Status Colors:
  Success → Green  (#10b981)
  Warning → Yellow (#f59e0b)
  Error   → Red    (#ef4444)
  Info    → Blue   (#3b82f6)
```

---

## Calculation Examples

### Example 1: Normal Drop-off
```
Applied: 100 candidates
Screening: 65 candidates

Dropped = 100 - 65 = 35
Drop-off Rate = (35 / 100) * 100 = 35%
Conversion Rate = 100 - 35 = 65%
Is Abnormal = 35 > 60 = FALSE ✅
```

### Example 2: Abnormal Drop-off
```
Interview: 50 candidates
Selected: 8 candidates

Dropped = 50 - 8 = 42
Drop-off Rate = (42 / 50) * 100 = 84%
Conversion Rate = 100 - 84 = 16%
Is Abnormal = 84 > 60 = TRUE ⚠️
```

---

## API Request/Response Example

### Request
```http
GET /api/analytics/diagnostic-funnel HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Response
```json
{
  "stages": [
    {"stage": "Applied", "count": 150, "percentage": 100.0},
    {"stage": "Screening", "count": 85, "percentage": 56.7},
    {"stage": "Interview", "count": 45, "percentage": 30.0},
    {"stage": "Selected", "count": 12, "percentage": 8.0}
  ],
  "dropoffs": [
    {
      "from_stage": "Applied",
      "to_stage": "Screening",
      "dropped_count": 65,
      "dropoff_rate": 43.3,
      "conversion_rate": 56.7,
      "is_abnormal": false,
      "reason": "Skills mismatch with requirements"
    },
    {
      "from_stage": "Screening",
      "to_stage": "Interview",
      "dropped_count": 40,
      "dropoff_rate": 47.1,
      "conversion_rate": 52.9,
      "is_abnormal": false,
      "reason": "Scheduling delays or candidate unavailability"
    },
    {
      "from_stage": "Interview",
      "to_stage": "Selected",
      "dropped_count": 33,
      "dropoff_rate": 73.3,
      "conversion_rate": 26.7,
      "is_abnormal": true,
      "reason": "Performance below expectations or high competition"
    }
  ],
  "total_candidates": 150,
  "rejected_total": 45,
  "rejection_rate": 30.0
}
```

---

## Error Handling Flow

```
API Call
  │
  ├─ Success → Render funnel
  │
  ├─ Network Error → Show loading spinner
  │
  ├─ Auth Error → Redirect to login
  │
  └─ Server Error → Show error message
      │
      └─ Fallback: Show empty state
```

---

## Performance Optimization

```
Backend:
  ├─ Single database query per stage (4 queries total)
  ├─ Parallel AI requests (if multiple drop-offs)
  └─ Response caching (optional)

Frontend:
  ├─ Lazy load modal (only when clicked)
  ├─ Memoize calculations
  └─ Debounce user interactions
```

This visual guide complements the detailed documentation and provides a quick reference for understanding the system architecture!
