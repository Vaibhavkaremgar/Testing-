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
            "technology": re.compile(r"(?i)\b(?:python|java|sql|aws|docker|react|fastapi|backend|frontend|machine learning)\b"),
            "sales": re.compile(r"(?i)\b(?:sales|business development|lead generation|crm|territory|pipeline)\b"),
            "healthcare": re.compile(r"(?i)\b(?:patient|clinical|hospital|nurse|physician|medical|treatment)\b"),
            "hospitality": re.compile(r"(?i)\b(?:hotel|guest|front desk|housekeeping|tourism|food|beverage)\b"),
            "finance": re.compile(r"(?i)\b(?:banking|investment|accounting|audit|financial|budget|tally)\b"),
            "hr": re.compile(r"(?i)\b(?:recruitment|hiring|onboarding|payroll|talent acquisition|employee)\b"),
        }
        normalized = str(text or "")
        scores = {t: len(p.findall(normalized)) for t, p in RESUME_TYPE_PATTERNS.items()}
        best_type = max(scores, key=scores.get) if scores else "general"
        if not scores or scores.get(best_type, 0) == 0:
            best_type = "general"
        return {"resume_type": best_type, "resume_type_scores": scores}
