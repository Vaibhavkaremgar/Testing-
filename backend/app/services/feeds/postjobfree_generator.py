from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from xml.etree import ElementTree as ET

from app.models import JobDescription
from app.services.feeds.base import BaseFeedGenerator
from app.services.public_jobs import build_location, build_public_job_url
from app.utils.xml_utils import append_text_element, prettify_xml, validate_xml


POSTJOBFREE_CONTACT_EMAIL = "hr@mycompany.com"
POSTJOBFREE_CPC = "0.30"


def _format_postjobfree_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def generate_postjobfree_xml(jobs: Iterable[JobDescription]) -> bytes:
    root = ET.Element("source")

    for job in jobs:
        item = ET.SubElement(root, "job")
        append_text_element(item, "title", job.title)
        append_text_element(item, "date", _format_postjobfree_datetime(job.created_at))
        append_text_element(item, "referencenumber", str(job.id) if job.id is not None else "")
        append_text_element(item, "url", build_public_job_url(job))
        append_text_element(item, "company", job.company_name)
        append_text_element(item, "location", build_location(job))
        append_text_element(item, "description", job.description)
        append_text_element(item, "salary", job.salary_range)
        append_text_element(item, "email", POSTJOBFREE_CONTACT_EMAIL)
        append_text_element(item, "cpc", POSTJOBFREE_CPC)

    xml_content = prettify_xml(root)
    validate_xml(xml_content)
    return xml_content


class PostJobFreeFeedGenerator(BaseFeedGenerator):
    portal_name = "postjobfree"

    def build_feed(self, jobs: Iterable[JobDescription]) -> bytes:
        return generate_postjobfree_xml(jobs)
