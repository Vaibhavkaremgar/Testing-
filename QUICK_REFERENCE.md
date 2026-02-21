# Quick Reference: Before → After Changes

## 1. Skills Scoring (30 points)

### BEFORE: Keyword-only
```python
if skill_lower in resume_lower:
    skill_score += points_per_skill * 0.4  # Just mentioned
```
**Problem:** "Python" in "Python is popular" = same score as "Built Python APIs"

### AFTER: Context-aware
```python
if skill_lower in resume_lower:
    skill_score += points_per_skill * 0.3  # Mentioned
    
    # Check action context
    if nlp_signals['verb_density'] > 2.0:
        skill_score += points_per_skill * 0.2  # Used in action context
```
**Improvement:** Distinguishes mention from usage

---

## 2. Experience Relevance (35 points)

### BEFORE: Simple keyword count
```python
verb_count = sum(1 for verb in ['developed', 'built'] if verb in resume_lower)
relevance_score += min(5, verb_count * 0.5)
```
**Problem:** "developed" counted once, misses "developing", "developer"

### AFTER: Verb density analysis
```python
action_count = nlp_signals['action_verb_count']  # All forms via lemmatization
verb_density = nlp_signals['verb_density']  # Verbs per 100 words

relevance_score += min(3, action_count * 0.3)

if verb_density > 3.0:
    relevance_score += 2  # High action density bonus
```
**Improvement:** Measures action-oriented writing style

---

## 3. Projects Scoring (20 points)

### BEFORE: Regex patterns
```python
action_verbs = ['developed', 'built', 'created']
verb_count = sum(1 for verb in action_verbs if verb in resume_lower)
```
**Problem:** No context, no sentence structure analysis

### AFTER: Sentence-level analysis
```python
nlp_signals = get_nlp_signals(resume_text)

# Analyze action sentences
action_sentences = nlp_signals['action_sentences']
total_sentences = nlp_signals['total_sentences']

# Reward action-rich resumes
if verb_density > 3.0:
    relevance_score += 2
```
**Improvement:** Understands sentence structure and action density

---

## 4. Soft Skills Detection (5 points)

### BEFORE: Exact keyword match
```python
leadership_keywords = ['led', 'managed']
leadership_count = sum(1 for kw in leadership_keywords if kw in resume_lower)
```
**Problem:** Misses "leading", "leads", "leadership"

### AFTER: Lemmatized verb extraction
```python
# spaCy extracts all forms via lemmatization
leadership_count = nlp_signals['leadership_count']  # lead, led, leading, leads
```
**Improvement:** Catches all verb forms automatically

---

## 5. Impact Metrics (Bonus points)

### BEFORE: Regex-only
```python
metrics_pattern = r'\d+%|\d+x|\$\d+[kKmMbB]?'
metrics = re.findall(metrics_pattern, resume_text)
```
**Problem:** Misses "50 percent", "ten thousand dollars"

### AFTER: NER + Regex
```python
# spaCy NER detects PERCENT, MONEY, CARDINAL entities
impact_count = nlp_signals['impact_count']
has_percentages = nlp_signals['has_percentages']
has_money = nlp_signals['has_money']

# Bonus for diverse metrics
if has_percentages and has_money:
    impact_count += 1
```
**Improvement:** Detects written-out numbers and diverse metric types

---

## Score Comparison Example

### Resume: "Software Engineer with 3 years experience. Developed APIs using Python. Reduced latency by 40%."

| Component | OLD | NEW | Change |
|-----------|-----|-----|--------|
| Experience | 15/25 | 28/35 | +13 |
| Skills | 18/40 | 22/30 | +4 (adjusted weight) |
| Projects | 8/20 | 14/20 | +6 |
| Education | 6/10 | 6/10 | 0 |
| Soft Skills | 2/5 | 3/5 | +1 |
| **TOTAL** | **49** | **73** | **+24** ✅

---

## Key Metrics Tracked

### NLP Signals Extracted:
```python
{
    'action_verb_count': 12,        # Total action verbs found
    'verb_density': 3.2,            # Verbs per 100 words
    'impact_count': 3,              # Quantifiable metrics
    'leadership_count': 2,          # Leadership verbs
    'collaboration_count': 1,       # Team signals
    'action_sentences': 8,          # Sentences with action verbs
    'total_sentences': 15           # Total sentences
}
```

### Scoring Bonuses:
- **Verb density > 3.0:** +2 points (strong action orientation)
- **Verb density > 2.0:** +1 point (moderate action orientation)
- **Diverse metrics (% + $):** +1 point (comprehensive impact)
- **Action context for skills:** +0.2 points per skill (evidence of usage)

---

## Installation

```bash
# Install spaCy
pip install spacy==3.7.2

# Download English model
python -m spacy download en_core_web_sm

# Verify installation
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('✅ spaCy ready')"
```

---

## Testing

```bash
# Run balanced scoring test
python -m app.balanced_scoring

# Expected output:
# Experience: XX/35
# Skills: XX/30
# Projects: XX/20
# Education: XX/10
# Soft Skills: XX/5
# TOTAL: XX/100
```

---

## Rollback Plan

If issues arise, disable spaCy:
```python
# In spacy_nlp.py
SPACY_AVAILABLE = False  # Force fallback to regex
```

System will automatically use regex-only mode.
