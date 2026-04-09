results = {}

# FIX 1
with open('app/routes/candidates.py', 'rb') as f:
    c = f.read()
results['FIX1 fast_mode in extract_resume_data'] = b'parse_resume(file_path, original_filename, fast_mode=fast_mode)' in c
results['FIX1 fast_mode in process_saved_resume'] = b'fast_mode=fast_mode' in c

# FIX 2
with open('app/main.py', 'rb') as f:
    c = f.read()
results['FIX2 spaCy pre-warm'] = b'[STARTUP] Pre-warming spaCy' in c
results['FIX2 SkillIntelligence pre-warm'] = b'[STARTUP] Pre-warming SkillIntelligence' in c

# FIX 3
with open('app/routes/candidates.py', 'rb') as f:
    c = f.read()
results['FIX3 resume_text[:2000]'] = b'resume_text[:2000]' in c
results['FIX3 job_description[:2000]'] = b'job_description[:2000]' in c

# FIX 4
with open('ats/extraction/entity_extraction.py', 'rb') as f:
    c = f.read()
results['FIX4 combined_window'] = b'combined_window' in c
results['FIX4 no loop over search_windows'] = b'for window in search_windows' not in c

# FIX 5 + 6
with open('ats/extraction/resume_parser.py', 'rb') as f:
    c = f.read()
results['FIX5 NAME_COMPANY_PATTERN guard in _extract_name'] = b'FIX 5' in c
results['FIX6 _normalize_name_candidate(clean_name) guard'] = b'_normalize_name_candidate(clean_name)' in c

# FIX 7
with open('ats/extraction/experience_extraction.py', 'rb') as f:
    c = f.read()
results['FIX7 _normalize_company_key helper'] = b'def _normalize_company_key' in c
results['FIX7 key uses _normalize_company_key'] = b'_normalize_company_key(entry.get' in c

for k, v in results.items():
    status = 'OK' if v else 'MISSING'
    print(f'[{status}] {k}')
