import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models import JobDescription
from app.services.public_jobs import build_location, normalize_skills


_SALARY_TOKEN_RE = re.compile(r"(?P<currency>[A-Za-z$]+)?\s*(?P<value>\d+(?:[,\d]*)(?:\.\d+)?)", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(value: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {
            key: _prune_empty(item)
            for key, item in value.items()
        }
        return {
            key: item
            for key, item in cleaned.items()
            if item not in (None, "", [], {})
        }
    if isinstance(value, list):
        cleaned_items = [_prune_empty(item) for item in value]
        return [item for item in cleaned_items if item not in (None, "", [], {})]
    return value


def _job_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _salary_currency(symbol: str | None, unit_text: str) -> str:
    normalized = (symbol or "").strip().upper()
    if normalized in {"$", "USD"} or "usd" in unit_text:
        return "USD"
    if normalized in {"INR", "RS", "RUPEES"} or "inr" in unit_text or "rupee" in unit_text:
        return "INR"
    if normalized in {"EUR"} or "eur" in unit_text:
        return "EUR"
    if normalized in {"GBP"} or "gbp" in unit_text:
        return "GBP"
    return "USD"


def _parse_salary_range(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None

    matches = list(_SALARY_TOKEN_RE.finditer(value))
    if not matches:
        return None

    unit_text = value.lower()
    amounts: list[Decimal] = []
    currency_symbol = None

    for match in matches[:2]:
        token = match.group("value").replace(",", "")
        currency_symbol = currency_symbol or match.group("currency")
        try:
            amounts.append(Decimal(token))
        except InvalidOperation:
            continue

    if not amounts:
        return None

    unit = "YEAR"
    if any(token in unit_text for token in ("hour", "/hr", "hourly")):
        unit = "HOUR"
    elif any(token in unit_text for token in ("month", "/mo", "monthly")):
        unit = "MONTH"
    elif any(token in unit_text for token in ("week", "weekly")):
        unit = "WEEK"
    elif any(token in unit_text for token in ("day", "daily")):
        unit = "DAY"

    amount_payload: dict[str, Any]
    if len(amounts) >= 2:
        low, high = amounts[0], amounts[1]
        amount_payload = {
            "@type": "QuantitativeValue",
            "minValue": float(min(low, high)),
            "maxValue": float(max(low, high)),
            "unitText": unit,
        }
    else:
        amount_payload = {
            "@type": "QuantitativeValue",
            "value": float(amounts[0]),
            "unitText": unit,
        }

    return {
        "@type": "MonetaryAmount",
        "currency": _salary_currency(currency_symbol, unit_text),
        "value": amount_payload,
    }


def _build_google_base_salary(job: JobDescription) -> dict[str, Any] | None:
    parsed_salary = _parse_salary_range(job.salary_range)
    if parsed_salary is not None:
        return parsed_salary

    salary_value = _clean_text(job.salary_range)
    if not salary_value:
        return None

    return {
        "@type": "MonetaryAmount",
        "currency": "INR",
        "value": {
            "@type": "QuantitativeValue",
            "value": salary_value,
            "unitText": "YEAR",
        },
    }


def build_google_job_posting_schema(job: JobDescription) -> dict[str, Any]:
    company_name = _clean_text(job.company_name) or "Pontis"
    description_parts = [
        _clean_text(job.description),
        _clean_text(job.responsibilities),
        _clean_text(job.requirements),
    ]
    description = "\n\n".join(part for part in description_parts if part)

    job_schema = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": _clean_text(job.title),
        "description": description or f"Apply for { _clean_text(job.title) or 'this role' } at {company_name}.",
        "identifier": {
            "@type": "PropertyValue",
            "name": "Pontis",
            "value": str(job.id),
        },
        "datePosted": _job_datetime(job.created_at),
        "validThrough": _job_datetime(job.valid_through),
        "employmentType": _clean_text(job.employment_type) or None,
        "hiringOrganization": {
            "@type": "Organization",
            "name": _clean_text(job.company_name) or "Pontis",
            "sameAs": _clean_text(job.company_website_url) or "https://pontis.one",
            "logo": _clean_text(job.company_logo_url) or None,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": _clean_text(job.city) or None,
                "addressRegion": _clean_text(job.state) or None,
                "addressCountry": _clean_text(job.country) or None,
            },
        },
        "baseSalary": _build_google_base_salary(job),
        "directApply": True,
    }

    if bool(job.remote):
        job_schema["jobLocationType"] = "TELECOMMUTE"
        applicant_country = _clean_text(job.country)
        if applicant_country:
            job_schema["applicantLocationRequirements"] = {
                "@type": "Country",
                "name": applicant_country,
            }

    return _prune_empty(job_schema)


def build_job_posting_schema(
    job: JobDescription,
    *,
    job_url: str,
    applicant_location: str | None,
) -> dict[str, Any]:
    google_schema = build_google_job_posting_schema(job)
    company_name = _clean_text(job.company_name) or "Confidential Company"
    location = build_location(job)
    is_remote = bool(job.remote)

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": _clean_text(job.title),
        "description": _clean_text(job.description),
        "identifier": {
            "@type": "PropertyValue",
            "name": company_name,
            "value": str(job.job_id or job.id),
        },
        "datePosted": _job_datetime(job.created_at),
        "validThrough": _job_datetime(job.valid_through),
        "employmentType": _clean_text(job.employment_type) or None,
        "hiringOrganization": {
            "@type": "Organization",
            "name": company_name,
            "sameAs": _clean_text(job.company_website_url) or job_url,
            "logo": _clean_text(job.company_logo_url) or None,
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": location or None,
                "addressLocality": _clean_text(job.city) or None,
                "addressRegion": _clean_text(job.state) or None,
                "addressCountry": _clean_text(job.country) or None,
            },
        },
        "baseSalary": _parse_salary_range(job.salary_range),
        "directApply": True,
        "applicantLocationRequirements": (
            {
                "@type": "Country",
                "name": applicant_location,
            }
            if applicant_location
            else None
        ),
        "jobLocationType": "TELECOMMUTE" if is_remote else None,
        "industry": _clean_text(job.industry) or _clean_text(job.category) or None,
        "skills": normalize_skills(job.skills) or None,
        "responsibilities": _clean_text(job.responsibilities) or None,
        "qualifications": _clean_text(job.requirements) or None,
        "experienceRequirements": _clean_text(job.experience_required) or None,
        "url": job_url,
    }

    if not is_remote:
        schema.pop("jobLocationType", None)
    if not applicant_location:
        schema.pop("applicantLocationRequirements", None)

    schema["hiringOrganization"] = {
        **google_schema.get("hiringOrganization", {}),
        **schema["hiringOrganization"],
    }
    schema["jobLocation"]["address"] = {
        **google_schema.get("jobLocation", {}).get("address", {}),
        **schema["jobLocation"]["address"],
    }

    merged_schema = {
        **google_schema,
        **schema,
        "hiringOrganization": schema["hiringOrganization"],
        "jobLocation": schema["jobLocation"],
    }
    return _prune_empty(merged_schema)


def dump_job_posting_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=True, separators=(",", ":"))
