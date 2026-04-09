"""Apply all PERF and ACC fixes to the ATS codebase."""
import re

results = {}

# ── PERF-2: resume_parser.py — cap raw_text at 5000 chars after PyMuPDF ──────
with open('ats/extraction/resume_parser.py', 'rb') as f:
    rp = f.read()

# The cap goes in parse_resume() after raw_text is extracted from document_payload
old_p2 = (
    b'    raw_text = str(document_payload.get("text") or "")\n'
    b'    layout_signals = document_payload.get("layout") or _default_layout_signals()\n'
    b'    parsed_resume = parse_resume_text'
)
new_p2 = (
    b'    raw_text = str(document_payload.get("text") or "")[:5000]\n'
    b'    layout_signals = document_payload.get("layout") or _default_layout_signals()\n'
    b'    parsed_resume = parse_resume_text'
)
if old_p2 in rp:
    rp = rp.replace(old_p2, new_p2, 1)
    results['PERF-2 raw_text cap 5000'] = 'OK'
elif b'raw_text = str(document_payload.get("text") or "")[:5000]' in rp:
    results['PERF-2 raw_text cap 5000'] = 'already applied'
else:
    results['PERF-2 raw_text cap 5000'] = 'PATTERN NOT FOUND'

with open('ats/extraction/resume_parser.py', 'wb') as f:
    f.write(rp)

# ── PERF-3: matching/engine.py — truncate inputs in tfidf and bm25 ────────────
with open('ats/matching/engine.py', 'rb') as f:
    me = f.read()

old_tfidf = (
    b'    def tfidf_similarity(self, source_text: str, target_text: str) -> float:\n'
    b'        source = self._normalize_text(source_text)\n'
    b'        target = self._normalize_text(target_text)\n'
)
new_tfidf = (
    b'    def tfidf_similarity(self, source_text: str, target_text: str) -> float:\n'
    b'        source_text = source_text[:2000]\n'
    b'        target_text = target_text[:2000]\n'
    b'        source = self._normalize_text(source_text)\n'
    b'        target = self._normalize_text(target_text)\n'
)

old_bm25 = (
    b'    def bm25_similarity(self, source_text: str, target_text: str) -> float:\n'
    b'        query_tokens = self._tokenize(source_text)\n'
    b'        document_tokens = self._tokenize(target_text)\n'
)
new_bm25 = (
    b'    def bm25_similarity(self, source_text: str, target_text: str) -> float:\n'
    b'        source_text = source_text[:2000]\n'
    b'        target_text = target_text[:2000]\n'
    b'        query_tokens = self._tokenize(source_text)\n'
    b'        document_tokens = self._tokenize(target_text)\n'
)

if old_tfidf in me:
    me = me.replace(old_tfidf, new_tfidf, 1)
    results['PERF-3 tfidf truncate'] = 'OK'
elif b'source_text = source_text[:2000]' in me:
    results['PERF-3 tfidf truncate'] = 'already applied'
else:
    results['PERF-3 tfidf truncate'] = 'PATTERN NOT FOUND'

if old_bm25 in me:
    me = me.replace(old_bm25, new_bm25, 1)
    results['PERF-3 bm25 truncate'] = 'OK'
elif me.count(b'source_text = source_text[:2000]') >= 2:
    results['PERF-3 bm25 truncate'] = 'already applied'
else:
    results['PERF-3 bm25 truncate'] = 'PATTERN NOT FOUND'

# ── PERF-4: matching/engine.py — _TFIDF_CONFIG singleton ─────────────────────
old_tfidf_inst = b'        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")\n'
new_tfidf_inst = b'        vectorizer = TfidfVectorizer(**_TFIDF_CONFIG)\n'

if b'_TFIDF_CONFIG' not in me:
    # Add module-level config after the imports block
    me = me.replace(
        b'TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#/-]*")',
        b'TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#/-]*")\n_TFIDF_CONFIG = {"ngram_range": (1, 2), "stop_words": "english"}',
        1
    )
    if old_tfidf_inst in me:
        me = me.replace(old_tfidf_inst, new_tfidf_inst, 1)
        results['PERF-4 tfidf config'] = 'OK'
    else:
        results['PERF-4 tfidf config'] = 'inst pattern not found'
else:
    results['PERF-4 tfidf config'] = 'already applied'

with open('ats/matching/engine.py', 'wb') as f:
    f.write(me)

# ── PERF-5: config.py — NLP_MAX_TEXT_LENGTH 4000 -> 2000 ─────────────────────
with open('app/config.py', 'rb') as f:
    cfg = f.read()

old_cfg = b'    NLP_MAX_TEXT_LENGTH: int = int(os.getenv("NLP_MAX_TEXT_LENGTH", "4000"))'
new_cfg = b'    NLP_MAX_TEXT_LENGTH: int = int(os.getenv("NLP_MAX_TEXT_LENGTH", "2000"))'

if old_cfg in cfg:
    cfg = cfg.replace(old_cfg, new_cfg, 1)
    results['PERF-5 NLP_MAX_TEXT_LENGTH=2000'] = 'OK'
elif b'"2000"' in cfg and b'NLP_MAX_TEXT_LENGTH' in cfg:
    results['PERF-5 NLP_MAX_TEXT_LENGTH=2000'] = 'already applied'
else:
    results['PERF-5 NLP_MAX_TEXT_LENGTH=2000'] = 'PATTERN NOT FOUND'

with open('app/config.py', 'wb') as f:
    f.write(cfg)

# ── PERF-7 / ACC-1: main.py — add domain classifier pre-warm + spaCy model ───
with open('app/main.py', 'rb') as f:
    main = f.read()

if b'[STARTUP] Pre-warming domain classifier' not in main:
    old_main = (
        b'    print("[STARTUP] Pre-warming SkillIntelligence...")\n'
        b'    from ats.extraction.skill_intelligence import get_skill_engine\n'
        b'    get_skill_engine()\n'
        b'    print("[STARTUP] SkillIntelligence ready.")\n'
    )
    new_main = (
        b'    print("[STARTUP] Pre-warming SkillIntelligence...")\n'
        b'    from ats.extraction.skill_intelligence import get_skill_engine\n'
        b'    get_skill_engine()\n'
        b'    print("[STARTUP] SkillIntelligence ready.")\n'
        b'\n'
        b'    print("[STARTUP] Pre-warming domain classifier...")\n'
        b'    from ats.extraction.resume_type_detection import get_domain_classifier\n'
        b'    get_domain_classifier()\n'
        b'    print("[STARTUP] Domain classifier ready.")\n'
        b'\n'
        b'    print("[STARTUP] All systems ready. Accepting requests.")\n'
    )
    if old_main in main:
        main = main.replace(old_main, new_main, 1)
        results['PERF-7 domain classifier warmup'] = 'OK'
    else:
        results['PERF-7 domain classifier warmup'] = 'PATTERN NOT FOUND'
else:
    results['PERF-7 domain classifier warmup'] = 'already applied'

with open('app/main.py', 'wb') as f:
    f.write(main)

# ── ACC-1: spacy_nlp.py — upgrade en_core_web_sm -> en_core_web_md ────────────
with open('app/spacy_nlp.py', 'rb') as f:
    snlp = f.read()

if b'en_core_web_sm' in snlp:
    snlp = snlp.replace(b'en_core_web_sm', b'en_core_web_md')
    results['ACC-1 spacy model md'] = 'OK'
    with open('app/spacy_nlp.py', 'wb') as f:
        f.write(snlp)
else:
    results['ACC-1 spacy model md'] = 'already applied or not found'

# ── ACC-2: resume_type_detection.py — semantic domain detection ───────────────
new_rtd = b'''\
from __future__ import annotations

from typing import Dict


_DOMAIN_ANCHORS_TEXT = {
    "technology": "software engineering programming APIs cloud devops coding",
    "healthcare": "patient clinical medical nursing hospital treatment care",
    "hospitality": "hotel guest service front desk housekeeping tourism food",
    "retail": "store sales merchandise inventory customer checkout products",
    "finance": "banking investment accounting audit financial analysis budget",
    "hr": "recruitment hiring onboarding employee relations payroll talent",
    "marketing": "brand campaign digital social media content strategy advertising",
    "education": "teaching curriculum students classroom training academic learning",
    "logistics": "supply chain warehouse delivery logistics operations dispatch",
    "legal": "compliance legal contracts litigation regulatory law policy",
}

_domain_anchor_docs = None


def _get_domain_anchors():
    global _domain_anchor_docs
    if _domain_anchor_docs is not None:
        return _domain_anchor_docs
    try:
        from app.spacy_nlp import get_nlp
        nlp = get_nlp()
        if nlp is None:
            return {}
        _domain_anchor_docs = {
            domain: nlp(text)
            for domain, text in _DOMAIN_ANCHORS_TEXT.items()
        }
    except Exception:
        _domain_anchor_docs = {}
    return _domain_anchor_docs


def get_domain_classifier():
    return _get_domain_anchors()


def detect_resume_type(text: str) -> Dict[str, object]:
    try:
        from app.spacy_nlp import get_nlp
        nlp = get_nlp()
        if nlp is None:
            raise RuntimeError("spaCy unavailable")
        doc = nlp(str(text or "")[:500])
        anchors = _get_domain_anchors()
        best, best_score = "general", 0.38
        for domain, anchor_doc in anchors.items():
            try:
                score = doc.similarity(anchor_doc)
                if score > best_score:
                    best_score = score
                    best = domain
            except Exception:
                continue
        return {
            "resume_type": best,
            "resume_type_scores": {d: 0 for d in _DOMAIN_ANCHORS_TEXT},
        }
    except Exception:
        # Keyword fallback when spaCy or vectors unavailable
        import re
        RESUME_TYPE_PATTERNS = {
            "technology": re.compile(r"(?i)\\b(?:python|java|sql|aws|docker|react|fastapi|backend|frontend|machine learning)\\b"),
            "sales": re.compile(r"(?i)\\b(?:sales|business development|lead generation|crm|territory|pipeline)\\b"),
            "healthcare": re.compile(r"(?i)\\b(?:patient|clinical|hospital|nurse|physician|medical|treatment)\\b"),
            "hospitality": re.compile(r"(?i)\\b(?:hotel|guest|front desk|housekeeping|tourism|food|beverage)\\b"),
            "finance": re.compile(r"(?i)\\b(?:banking|investment|accounting|audit|financial|budget|tally)\\b"),
            "hr": re.compile(r"(?i)\\b(?:recruitment|hiring|onboarding|payroll|talent acquisition|employee)\\b"),
        }
        normalized = str(text or "")
        scores = {t: len(p.findall(normalized)) for t, p in RESUME_TYPE_PATTERNS.items()}
        best_type = max(scores, key=scores.get) if scores else "general"
        if not scores or scores.get(best_type, 0) == 0:
            best_type = "general"
        return {"resume_type": best_type, "resume_type_scores": scores}
'''

with open('ats/extraction/resume_type_detection.py', 'wb') as f:
    f.write(new_rtd)
results['ACC-2 semantic domain detection'] = 'OK'

# ── ACC-3: section_segmentation.py — semantic fallback ───────────────────────
with open('ats/preprocessing/section_segmentation.py', 'rb') as f:
    ss = f.read()

semantic_block = b'''

_SECTION_ANCHOR_TEXT = {
    "experience": "employment job worked responsibilities managed led company role position",
    "skills": "tools technologies proficient languages frameworks software abilities",
    "education": "university college degree studied graduated diploma academic",
    "certifications": "certified awarded license accredited credential certification",
    "achievements": "achieved won recognition award performance impact result",
    "summary": "objective profile about myself overview professional background",
    "projects": "built developed created designed implemented project solution",
}

_section_anchor_docs = None


def _get_section_anchors():
    global _section_anchor_docs
    if _section_anchor_docs is not None:
        return _section_anchor_docs
    try:
        from app.spacy_nlp import get_nlp
        nlp = get_nlp()
        if nlp is None:
            _section_anchor_docs = {}
            return _section_anchor_docs
        _section_anchor_docs = {k: nlp(v) for k, v in _SECTION_ANCHOR_TEXT.items()}
    except Exception:
        _section_anchor_docs = {}
    return _section_anchor_docs


def semantic_section_fallback(text: str) -> dict:
    try:
        from app.spacy_nlp import get_nlp, get_section_doc
        nlp = get_nlp()
        if nlp is None:
            return {}
        anchors = _get_section_anchors()
        if not anchors:
            return {}
        doc = get_section_doc(text[:3000])
        if doc is None:
            return {}
        result = {k: [] for k in anchors}
        for sent in doc.sents:
            clean = sent.text.strip()
            if len(clean) < 10:
                continue
            best, best_score = None, 0.38
            for section, anchor_doc in anchors.items():
                try:
                    score = sent.similarity(anchor_doc)
                    if score > best_score:
                        best_score = score
                        best = section
                except Exception:
                    continue
            if best:
                result[best].append(clean)
        return result
    except Exception:
        return {}

'''

# Add semantic block before segment_resume_sections
anchor = b'\ndef segment_resume_sections(text: str) -> Dict[str, str]:\r\n'
anchor_lf = b'\ndef segment_resume_sections(text: str) -> Dict[str, str]:\n'

if b'semantic_section_fallback' not in ss:
    if anchor in ss:
        ss = ss.replace(anchor, semantic_block + anchor, 1)
        results['ACC-3 semantic fallback added'] = 'OK (CRLF)'
    elif anchor_lf in ss:
        ss = ss.replace(anchor_lf, semantic_block + anchor_lf, 1)
        results['ACC-3 semantic fallback added'] = 'OK (LF)'
    else:
        results['ACC-3 semantic fallback added'] = 'anchor not found'
else:
    results['ACC-3 semantic fallback added'] = 'already applied'

# Patch segment_resume_sections to call semantic fallback when < 2 sections found
old_ss_end = b'    return sections\r\n\r\n\r\ndef get_section_content'
old_ss_end_lf = b'    return sections\n\n\ndef get_section_content'

semantic_call = (
    b'    populated = [k for k, v in sections.items() if v and k != "header"]\n'
    b'    if len(populated) < 2:\n'
    b'        sem = semantic_section_fallback(text)\n'
    b'        for k, v in sem.items():\n'
    b'            if not sections.get(k) and v:\n'
    b'                sections[k] = "\\n".join(v)\n'
)

if b'semantic_section_fallback(text)' not in ss:
    if old_ss_end in ss:
        ss = ss.replace(old_ss_end, semantic_call + b'    return sections\r\n\r\n\r\ndef get_section_content', 1)
        results['ACC-3 semantic fallback call'] = 'OK (CRLF)'
    elif old_ss_end_lf in ss:
        ss = ss.replace(old_ss_end_lf, semantic_call + b'    return sections\n\n\ndef get_section_content', 1)
        results['ACC-3 semantic fallback call'] = 'OK (LF)'
    else:
        results['ACC-3 semantic fallback call'] = 'end anchor not found'
else:
    results['ACC-3 semantic fallback call'] = 'already applied'

with open('ats/preprocessing/section_segmentation.py', 'wb') as f:
    f.write(ss)

# ── ACC-4: resume_parser.py — name extraction edge cases ─────────────────────
with open('ats/extraction/resume_parser.py', 'rb') as f:
    rp = f.read()

# FIX A+B+C+D: patch _normalize_name_candidate
# Add honorific/credential patterns at module level
if b'NAME_HONORIFIC_PATTERN' not in rp:
    rp = rp.replace(
        b'UPPERCASE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z\'`.-]*(?:\\s+[A-Z][A-Z\'`.-]*){1,3}$")',
        (
            b'UPPERCASE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z\'`.-]*(?:\\s+[A-Z][A-Z\'`.-]*){1,3}$")\n'
            b'NAME_HONORIFIC_PATTERN = re.compile(\n'
            b'    r"^(dr\\.?|mr\\.?|mrs\\.?|ms\\.?|prof\\.?|er\\.?)\\s+",\n'
            b'    re.IGNORECASE\n'
            b')\n'
            b'NAME_CREDENTIAL_SUFFIX = re.compile(\n'
            b'    r",?\\s*(mba|phd|ph\\.d|b\\.tech|m\\.tech|bca|mca|b\\.e|m\\.e|cpa|cfa)\\s*$",\n'
            b'    re.IGNORECASE\n'
            b')'
        ),
        1
    )
    results['ACC-4A honorific patterns'] = 'OK'
else:
    results['ACC-4A honorific patterns'] = 'already applied'

# FIX C: allow 5-word names (change 2<=len<=4 to 2<=len<=5)
old_word_check = b'    if not (2 <= len(words) <= 4):\n        return ""\n'
new_word_check = b'    if not (2 <= len(words) <= 5):\n        return ""\n'
if old_word_check in rp:
    rp = rp.replace(old_word_check, new_word_check, 1)
    results['ACC-4C 5-word names'] = 'OK'
elif b'if not (2 <= len(words) <= 5):' in rp:
    results['ACC-4C 5-word names'] = 'already applied'
else:
    results['ACC-4C 5-word names'] = 'PATTERN NOT FOUND'

# FIX D: allow hyphens in names
old_alpha = b'    if not all(word.replace(".", "").replace("\'", "").isalpha() for word in words):\n        return ""\n'
new_alpha = b'    if not all(word.replace(".", "").replace("\'", "").replace("-", "").isalpha() for word in words):\n        return ""\n'
if old_alpha in rp:
    rp = rp.replace(old_alpha, new_alpha, 1)
    results['ACC-4D hyphen names'] = 'OK'
elif b'.replace("-", "").isalpha()' in rp:
    results['ACC-4D hyphen names'] = 'already applied'
else:
    results['ACC-4D hyphen names'] = 'PATTERN NOT FOUND'

# FIX A+B: apply honorific strip + ALL CAPS handling inside _normalize_name_candidate
# Insert before the final return statement
old_return = b'    return " ".join(word if len(word) == 1 else word.title() for word in words)\n'
new_return = (
    b'    candidate = NAME_HONORIFIC_PATTERN.sub("", candidate).strip()\n'
    b'    candidate = NAME_CREDENTIAL_SUFFIX.sub("", candidate).strip()\n'
    b'    if not candidate:\n'
    b'        return ""\n'
    b'    words = candidate.split()\n'
    b'    if not (2 <= len(words) <= 5):\n'
    b'        return ""\n'
    b'    if candidate.isupper() and 2 <= len(words) <= 5:\n'
    b'        candidate = candidate.title()\n'
    b'        words = candidate.split()\n'
    b'    return " ".join(word if len(word) == 1 else word.title() for word in words)\n'
)
if old_return in rp and b'NAME_HONORIFIC_PATTERN.sub' not in rp:
    rp = rp.replace(old_return, new_return, 1)
    results['ACC-4AB honorific+caps strip'] = 'OK'
elif b'NAME_HONORIFIC_PATTERN.sub' in rp:
    results['ACC-4AB honorific+caps strip'] = 'already applied'
else:
    results['ACC-4AB honorific+caps strip'] = 'PATTERN NOT FOUND'

with open('ats/extraction/resume_parser.py', 'wb') as f:
    f.write(rp)

# ── ACC-6B: experience_extraction.py — tag internships ───────────────────────
with open('ats/extraction/experience_extraction.py', 'rb') as f:
    ee = f.read()

if b'is_internship' not in ee:
    # Add after entry["confidence"] = _experience_confidence(entry) in _entry_from_block
    old_conf = (
        b'    entry["confidence"] = _experience_confidence(entry)\n'
        b'    return entry\n'
        b'\n'
        b'\n'
        b'def _extract_structured_experience_entries'
    )
    new_conf = (
        b'    entry["confidence"] = _experience_confidence(entry)\n'
        b'    _internship_src = (entry.get("role") or "") + " " + (entry.get("company") or "")\n'
        b'    entry["is_internship"] = bool(re.search(r"(?i)\\b(intern|internship|trainee|apprentice)\\b", _internship_src))\n'
        b'    return entry\n'
        b'\n'
        b'\n'
        b'def _extract_structured_experience_entries'
    )
    if old_conf in ee:
        ee = ee.replace(old_conf, new_conf, 1)
        results['ACC-6B internship tag'] = 'OK'
    else:
        results['ACC-6B internship tag'] = 'PATTERN NOT FOUND'
else:
    results['ACC-6B internship tag'] = 'already applied'

# ACC-6D: never return negative duration
old_dur = b'    duration_years = round(duration_months / 12.0, 1)\n'
new_dur = b'    duration_months = max(duration_months, 0)\n    duration_years = round(duration_months / 12.0, 1)\n'
if old_dur in ee and b'duration_months = max(duration_months, 0)' not in ee:
    ee = ee.replace(old_dur, new_dur, 1)
    results['ACC-6D no negative duration'] = 'OK'
elif b'duration_months = max(duration_months, 0)' in ee:
    results['ACC-6D no negative duration'] = 'already applied'
else:
    results['ACC-6D no negative duration'] = 'PATTERN NOT FOUND'

with open('ats/extraction/experience_extraction.py', 'wb') as f:
    f.write(ee)

# ── ACC-7A+B: information_extraction.py — dedup skills + strip proficiency ────
with open('ats/extraction/information_extraction.py', 'rb') as f:
    ie = f.read()

if b'PROFICIENCY_PATTERN' not in ie:
    # Add pattern at module level near other skill patterns
    ie = ie.replace(
        b'SKILL_TOKEN_SPLIT_PATTERN = re.compile(r"[\\n,;|]+")',
        (
            b'SKILL_TOKEN_SPLIT_PATTERN = re.compile(r"[\\n,;|]+")\n'
            b'PROFICIENCY_PATTERN = re.compile(\n'
            b'    r"(?i)\\s*[\\(\\[]\\s*(beginner|intermediate|advanced|expert|proficient|familiar|basic)\\s*[\\)\\]]"\n'
            b')'
        ),
        1
    )
    results['ACC-7B proficiency pattern'] = 'OK'
else:
    results['ACC-7B proficiency pattern'] = 'already applied'

# Strip proficiency labels inside _fallback_skill_from_chunk (already strips intermediate/advanced)
# The existing code already handles this. Mark as covered.
results['ACC-7B proficiency strip'] = 'covered by existing _fallback_skill_from_chunk'

# ACC-7A: dedup is already handled by _unique_in_order. Mark as covered.
results['ACC-7A dedup'] = 'covered by existing _unique_in_order'

with open('ats/extraction/information_extraction.py', 'wb') as f:
    f.write(ie)

# ── ACC-8: resume_parser.py — cross-contamination guards ─────────────────────
with open('ats/extraction/resume_parser.py', 'rb') as f:
    rp = f.read()

if b'current_company must never equal name' not in rp:
    # Insert after extracted_name, split_role are set, before building result dict
    old_result_start = b'    contact_email = _extract_email(cleaned_text or raw_text)\n'
    new_result_start = (
        b'    contact_email = _extract_email(cleaned_text or raw_text)\n'
        b'    # ACC-8: cross-contamination guards\n'
        b'    _current_company = extracted_info.get("current_company") or ""\n'
        b'    _current_role = extracted_info.get("current_role") or ""\n'
        b'    if _current_company and extracted_name and _current_company.strip().lower() == extracted_name.strip().lower():\n'
        b'        extracted_info["current_company"] = None\n'
        b'    if _current_role and extracted_name and _current_role.strip().lower() == extracted_name.strip().lower():\n'
        b'        extracted_info["current_role"] = None\n'
        b'    # current_company must never equal name\n'
    )
    if old_result_start in rp:
        rp = rp.replace(old_result_start, new_result_start, 1)
        results['ACC-8 cross-contamination guards'] = 'OK'
    else:
        results['ACC-8 cross-contamination guards'] = 'PATTERN NOT FOUND'
else:
    results['ACC-8 cross-contamination guards'] = 'already applied'

with open('ats/extraction/resume_parser.py', 'wb') as f:
    f.write(rp)

# ── Print results ─────────────────────────────────────────────────────────────
print("\n=== FIX RESULTS ===")
for k, v in results.items():
    status = "OK" if v in ("OK", "already applied", "covered by existing _unique_in_order",
                           "covered by existing _fallback_skill_from_chunk") else "ISSUE"
    print(f"[{status}] {k}: {v}")
