import re

# ── FIX 6: resume_parser.py ──────────────────────────────────────────────────
with open('ats/extraction/resume_parser.py', 'rb') as f:
    content = f.read()

old6 = (
    b'    elif ROLE_KEYWORD_PATTERN.search(compact):\n'
    b'        role_match = ROLE_KEYWORD_PATTERN.search(compact)\n'
    b'        if role_match:\n'
    b'            clean_name = compact[:role_match.start()].strip(" ,|/-")\n'
    b'            detected_role = compact[role_match.start():].strip(" ,|/-")\n'
    b'\n'
    b'    blocked_terms'
)
new6 = (
    b'    elif ROLE_KEYWORD_PATTERN.search(compact):\n'
    b'        role_match = ROLE_KEYWORD_PATTERN.search(compact)\n'
    b'        if role_match:\n'
    b'            clean_name = compact[:role_match.start()].strip(" ,|/-")\n'
    b'            detected_role = compact[role_match.start():].strip(" ,|/-")\n'
    b'            if not _normalize_name_candidate(clean_name):\n'
    b'                clean_name = compact\n'
    b'                detected_role = ""\n'
    b'\n'
    b'    blocked_terms'
)

if old6 in content:
    content = content.replace(old6, new6, 1)
    with open('ats/extraction/resume_parser.py', 'wb') as f:
        f.write(content)
    print('FIX 6 applied OK')
else:
    print('FIX 6 PATTERN NOT FOUND')
    idx = content.find(b'elif ROLE_KEYWORD_PATTERN')
    print(repr(content[idx:idx+300]))

# ── FIX 7: experience_extraction.py ─────────────────────────────────────────
with open('ats/extraction/experience_extraction.py', 'rb') as f:
    exp = f.read()

# Check if already applied
if b'_normalize_company_key' in exp:
    print('FIX 7 already applied')
else:
    old7_helper_anchor = b'def _dedupe_entries('
    new7_helper = (
        b'_COMPANY_NOISE = re.compile(\n'
        b'    r"\\b(?:pvt|ltd|inc|llc|limited|technologies|technology|solutions|services|group|consulting|india|global)\\b",\n'
        b'    re.IGNORECASE\n'
        b')\n'
        b'\n'
        b'\n'
        b'def _normalize_company_key(name: str) -> str:\n'
        b'    if not name:\n'
        b'        return ""\n'
        b'    return _COMPANY_NOISE.sub("", name).strip().lower()\n'
        b'\n'
        b'\n'
        b'def _dedupe_entries('
    )
    if old7_helper_anchor in exp:
        exp = exp.replace(old7_helper_anchor, new7_helper, 1)
        print('FIX 7 helper inserted OK')
    else:
        print('FIX 7 anchor not found')

    # Now replace the dedup key
    old7_key = (
        b'        primary_key = (\n'
        b'            company,\n'
        b'            start_date,\n'
        b'            end_date,\n'
        b'        )'
    )
    new7_key = (
        b'        primary_key = (\n'
        b'            _normalize_company_key(entry.get("company", "")),\n'
        b'            start_date,\n'
        b'            end_date,\n'
        b'        )'
    )
    if old7_key in exp:
        exp = exp.replace(old7_key, new7_key, 1)
        print('FIX 7 key replaced OK')
    else:
        print('FIX 7 key pattern not found')
        idx = exp.find(b'primary_key = (')
        print(repr(exp[idx:idx+200]))

    with open('ats/extraction/experience_extraction.py', 'wb') as f:
        f.write(exp)

# ── FIX 2: main.py ───────────────────────────────────────────────────────────
with open('app/main.py', 'rb') as f:
    main = f.read()

if b'[STARTUP] Pre-warming spaCy' in main:
    print('FIX 2 already applied')
else:
    old2 = (
        b'    try:\n'
        b'        logger.info("Running ATS warmup")\n'
        b'        warmup_result = run_ats_warmup(force=False)\n'
    )
    new2 = (
        b'    print("[STARTUP] Pre-warming spaCy...")\n'
        b'    from app.spacy_nlp import get_nlp\n'
        b'    get_nlp()\n'
        b'    print("[STARTUP] spaCy ready.")\n'
        b'    print("[STARTUP] Pre-warming SkillIntelligence...")\n'
        b'    from ats.extraction.skill_intelligence import get_skill_engine\n'
        b'    get_skill_engine()\n'
        b'    print("[STARTUP] SkillIntelligence ready.")\n'
        b'\n'
        b'    try:\n'
        b'        logger.info("Running ATS warmup")\n'
        b'        warmup_result = run_ats_warmup(force=False)\n'
    )
    if old2 in main:
        main = main.replace(old2, new2, 1)
        with open('app/main.py', 'wb') as f:
            f.write(main)
        print('FIX 2 applied OK')
    else:
        print('FIX 2 pattern not found')
        idx = main.find(b'Running ATS warmup')
        print(repr(main[max(0,idx-100):idx+200]))
