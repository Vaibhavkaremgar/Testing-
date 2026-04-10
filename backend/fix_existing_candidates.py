"""
Repair script: fixes candidates whose names contain job titles
and candidates with experience_years=0 but have work_experience data.
Run on the server: python fix_existing_candidates.py
"""
import sys, os, re, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from app.database import SessionLocal
from app.models import Candidate

# Same expanded pattern as the fix
ROLE_STOP_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|analyst|consultant|architect|lead|intern|qa|automation|"
    r"tester|specialist|designer|director|officer|executive|associate|scientist|recruiter|"
    r"coordinator|generalist|administrator|founder|owner|head|vp|president|cto|cfo|coo|ceo)\b"
)

def clean_name(raw_name: str) -> str:
    """Strip job title from name if present."""
    if not raw_name:
        return raw_name
    match = ROLE_STOP_PATTERN.search(raw_name)
    if not match:
        return raw_name
    clean = raw_name[:match.start()].strip(" ,|-")
    # Must still have at least 2 words to be a valid name
    words = clean.split()
    if len(words) >= 2:
        return clean
    return raw_name  # can't safely clean, leave as-is

def fix_experience(candidate) -> float | None:
    """Re-calculate experience from work_experience entries if years=0 or None."""
    entries = candidate.work_experience or []
    if not entries:
        return candidate.experience_years

    from datetime import datetime
    current_year = datetime.utcnow().year
    intervals = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        start_raw = str(entry.get("start_date") or entry.get("start") or "")
        end_raw = str(entry.get("end_date") or entry.get("end") or "")
        start_match = re.search(r"(19|20)\d{2}", start_raw)
        end_match = re.search(r"(19|20)\d{2}", end_raw)
        if not start_match:
            continue
        start_year = int(start_match.group(0))
        is_current = any(kw in end_raw.lower() for kw in ["present", "current", "now", "ongoing"])
        end_year = current_year if (is_current or not end_match) else int(end_match.group(0))
        if end_year < start_year:
            continue
        intervals.append((start_year, end_year))

    if not intervals:
        return candidate.experience_years

    intervals.sort()
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    total = sum(e - s for s, e in merged)
    return round(float(total), 1) if total > 0 else candidate.experience_years


db = SessionLocal()
try:
    candidates = db.query(Candidate).all()
    fixed_names = 0
    fixed_exp = 0

    for c in candidates:
        changed = False

        # Fix name
        if c.name:
            new_name = clean_name(c.name)
            if new_name != c.name:
                print(f"  NAME: '{c.name}' -> '{new_name}'")
                c.name = new_name
                changed = True

        # Fix experience: re-calculate if 0 or None but has work_experience entries
        if (c.experience_years is None or c.experience_years == 0) and c.work_experience:
            new_exp = fix_experience(c)
            if new_exp and new_exp > 0 and new_exp != c.experience_years:
                print(f"  EXP ({c.name}): {c.experience_years} -> {new_exp}")
                c.experience_years = new_exp
                fixed_exp += 1
                changed = True

        if changed:
            fixed_names += 1

    db.commit()
    print(f"\nDone. Fixed {fixed_names} candidates ({fixed_exp} experience updates).")

except Exception as e:
    db.rollback()
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
finally:
    db.close()
