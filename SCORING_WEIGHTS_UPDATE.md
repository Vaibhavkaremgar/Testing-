# Resume Scoring System - Updated Weights

## New Scoring Distribution (Total: 100 points)

| Component                        | Weight | Rationale                         |
|----------------------------------|--------|-----------------------------------|
| **Experience relevance & depth** | **35** | Best predictor of job performance |
| **Skills / capability evidence** | **30** | Must exist, but not dominant      |
| **Projects & impact**            | **20** | Shows hands-on ability            |
| **Education & certifications**   | **10** | Supporting signal only            |
| **Soft skills & leadership**     | **5**  | Hard to prove in resumes          |

## Changes Made

### 1. Component Weight Adjustments

**BEFORE:**
- Skills: 40 points
- Experience: 25 points
- Projects: 20 points
- Education: 10 points
- Impact: 5 points

**AFTER:**
- Experience: 35 points (+10)
- Skills: 30 points (-10)
- Projects: 20 points (unchanged)
- Education: 10 points (unchanged)
- Soft Skills: 5 points (renamed from Impact)

### 2. Component Reordering

Components are now evaluated in priority order:
1. Experience (35%) - Primary predictor
2. Skills (30%) - Core capability
3. Projects (20%) - Practical evidence
4. Education (10%) - Supporting credential
5. Soft Skills (5%) - Leadership/collaboration

### 3. Soft Skills Component Enhancement

**Renamed:** "Impact Evidence" → "Soft Skills & Leadership"

**New Scoring Logic:**
- Leadership signals (0-2 pts): led, managed, coordinated, mentored
- Collaboration signals (0-2 pts): team, collaborated, cross-functional
- Impact metrics bonus (0-1 pt): quantifiable achievements

**spaCy Integration:**
- Uses NLP to detect leadership verbs
- Extracts collaboration patterns
- Identifies impact entities (PERCENT, MONEY, CARDINAL)

### 4. Experience Component Adjustment

**Penalty Update:**
- Old: Max -5 points for overqualification
- New: Max -7 points for overqualification (proportional to 35 points)

## Files Modified

1. `backend/app/balanced_scoring.py`
   - Updated all component weights
   - Renamed `calculate_impact_score()` → `calculate_soft_skills_score()`
   - Integrated spaCy NLP signals
   - Reordered components in output

2. `backend/app/routes/candidates.py`
   - Updated `enhanced_fallback_evaluation()` print statements
   - Updated component references in strengths/gaps logic
   - Updated AI analysis summary format

3. `backend/app/spacy_nlp.py` (NEW)
   - Added spaCy helper functions
   - Global model loading
   - Action verb extraction
   - Impact entity detection
   - Soft skill signal extraction

4. `backend/requirements.txt`
   - Added `spacy==3.7.2`

## Installation

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Testing

Run the test in `balanced_scoring.py`:

```bash
python -m app.balanced_scoring
```

Expected output:
```
Component Breakdown:
  Experience: XX/35
  Skills: XX/30
  Projects: XX/20
  Education: XX/10
  Soft Skills: XX/5
```

## Backward Compatibility

✅ Output structure unchanged (same JSON format)
✅ Graceful fallback if spaCy unavailable (regex mode)
✅ Existing API endpoints work without changes
✅ Database schema unchanged
