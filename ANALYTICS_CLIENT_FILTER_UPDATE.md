# Analytics Client Filter - Implementation Guide

## Changes Required

The frontend API client has been updated to pass filter parameters. Now update the backend endpoints.

### Backend File: `backend/app/routes/analytics.py`

Replace these 4 endpoint functions with the versions below:

---

### 1. Update `/time-to-hire` endpoint

Replace the existing `get_time_to_hire` function (around line 1050) with:

```python
@router.get("/time-to-hire", response_model=List[TimeToHireData])
def get_time_to_hire(
    date_range: Optional[str] = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    recruiter: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.stage == CandidateStage.SELECTED),
        current_user
    )
    query = _apply_analytics_filters(
        query,
        db,
        current_user,
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        recruiter=recruiter,
        client=client,
        department=department,
    )
    candidates = query.all()

    month_buckets = {}
    for candidate in candidates:
        if not candidate.created_at:
            continue
        month_key = candidate.created_at.strftime("%b")
        end_date = candidate.stage_updated_at or candidate.updated_at or candidate.created_at
        days = max(1, (end_date - candidate.created_at).days) if end_date else 1
        month_buckets.setdefault(month_key, []).append(days)

    if not month_buckets:
        return [
            TimeToHireData(month="Aug", avg_days=28.5),
            TimeToHireData(month="Sep", avg_days=32.1),
            TimeToHireData(month="Oct", avg_days=25.8),
            TimeToHireData(month="Nov", avg_days=30.2),
            TimeToHireData(month="Dec", avg_days=35.7),
            TimeToHireData(month="Jan", avg_days=27.3),
        ]

    return [
        TimeToHireData(month=month, avg_days=round(sum(days) / len(days), 1))
        for month, days in month_buckets.items()
    ]
```

---

### 2. Update `/skill-heatmap` endpoint

Replace the function signature (around line 1070) from:
```python
@router.get("/skill-heatmap", response_model=List[SkillHeatmapData])
def get_skill_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
```

To:
```python
@router.get("/skill-heatmap", response_model=List[SkillHeatmapData])
def get_skill_heatmap(
    date_range: Optional[str] = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    recruiter: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
```

Then replace this line (around line 1170):
```python
    # Get candidates with skills
    candidates = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.skills.isnot(None)),
        current_user
    ).all()
```

With:
```python
    # Get candidates with skills
    query = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.skills.isnot(None)),
        current_user
    )
    query = _apply_analytics_filters(
        query,
        db,
        current_user,
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        recruiter=recruiter,
        client=client,
        department=department,
    )
    candidates = query.all()
```

---

### 3. Update `/score-distribution` endpoint

Replace the existing `get_score_distribution` function (around line 1230) with:

```python
@router.get("/score-distribution", response_model=List[ScoreDistribution])
def get_score_distribution(
    date_range: Optional[str] = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    recruiter: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Define score ranges
    ranges = [
        ("0-20", 0, 20),
        ("21-40", 21, 40),
        ("41-60", 41, 60),
        ("61-80", 61, 80),
        ("81-100", 81, 100),
    ]
    
    result = []
    base_query = _apply_candidate_visibility(db.query(Candidate), current_user)
    base_query = _apply_analytics_filters(
        base_query,
        db,
        current_user,
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        recruiter=recruiter,
        client=client,
        department=department,
    )
    for range_label, min_score, max_score in ranges:
        count = base_query.filter(
            Candidate.resume_score >= min_score,
            Candidate.resume_score <= max_score
        ).count() or 0
        result.append(ScoreDistribution(range=range_label, count=count))
    
    return result
```

---

### 4. Update `/hiring-by-department` endpoint

Replace the existing `get_hiring_by_department` function (around line 1290) with:

```python
@router.get("/hiring-by-department")
def get_hiring_by_department(
    date_range: Optional[str] = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    recruiter: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    jobs_query = _apply_job_visibility(db.query(JobDescription), db, current_user)
    
    # Apply client filter to jobs
    role_name = _role_name(current_user)
    if role_name == UserRole.ADMIN.value and client and client != "all":
        jobs_query = jobs_query.filter(JobDescription.company_name == client)
    
    if department and department != "all":
        jobs_query = jobs_query.filter(JobDescription.department == department)
    
    jobs = jobs_query.all()
    
    # Group by department
    dept_data = {}
    for job in jobs:
        dept = job.department or "Other"
        if dept not in dept_data:
            dept_data[dept] = {"hired": 0, "open": 0}
        
        # Count selected candidates for this job
        hired_query = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage == CandidateStage.SELECTED
        )
        hired_query = _apply_candidate_visibility(hired_query, current_user)
        
        # Apply date filters to hired candidates
        if date_range or start_date or end_date:
            hired_query = _apply_analytics_filters(
                hired_query,
                db,
                current_user,
                date_range=date_range,
                start_date=start_date,
                end_date=end_date,
                recruiter=recruiter,
                client=None,  # Already filtered at job level
                department=None,  # Already filtered at job level
            )
        
        hired = hired_query.scalar() or 0
        
        # Count open positions (vacancies - hired)
        open_positions = max(0, (job.vacancies or 1) - hired)
        
        dept_data[dept]["hired"] += hired
        dept_data[dept]["open"] += open_positions
    
    # Convert to list format
    result = [
        {"department": dept, "hired": data["hired"], "open": data["open"]}
        for dept, data in dept_data.items()
    ]
    
    return result
```

---

## How to Apply

1. Open `backend/app/routes/analytics.py`
2. Find each function listed above
3. Replace with the new version
4. Save the file
5. Restart the backend server

## Testing

1. Go to Analytics page
2. Select a client from the dropdown
3. All widgets should now filter by that client
4. Verify data changes when switching clients

