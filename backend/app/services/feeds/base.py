import logging
from typing import Iterable
from xml.etree import ElementTree as ET

from app.models import JobDescription
from app.services.public_jobs import build_location, build_public_apply_url, build_public_job_url, normalize_skills
from app.utils.xml_utils import append_text_element, format_datetime, prettify_xml, validate_xml

logger = logging.getLogger(__name__)


class BaseFeedGenerator:
    portal_name = "default"
    root_tag = "jobs"
    item_tag = "job"

    def build_feed(self, jobs: Iterable[JobDescription]) -> bytes:
        root = ET.Element(self.root_tag)
        for job in jobs:
            item = ET.SubElement(root, self.item_tag)
            self.populate_job_node(item, job)

        xml_content = prettify_xml(root)
        validate_xml(xml_content)
        logger.info("Generated %s XML feed", self.portal_name)
        return xml_content

    def populate_job_node(self, parent: ET.Element, job: JobDescription) -> None:
        append_text_element(parent, "id", job.id)
        append_text_element(parent, "title", job.title)
        append_text_element(parent, "company", job.company_name)
        append_text_element(parent, "city", job.city)
        append_text_element(parent, "state", job.state)
        append_text_element(parent, "country", job.country)
        append_text_element(parent, "location", build_location(job))
        append_text_element(parent, "description", job.description)
        append_text_element(parent, "employment_type", job.employment_type)
        append_text_element(parent, "experience", job.experience_required)
        append_text_element(parent, "salary", job.salary_range)
        append_text_element(parent, "skills", self._render_skills(job.skills))
        append_text_element(parent, "category", job.category)
        append_text_element(parent, "remote", str(bool(job.remote)).lower())
        append_text_element(parent, "job_url", self._build_job_url(job))
        append_text_element(parent, "apply_url", self._build_apply_url(job))
        append_text_element(parent, "created_at", format_datetime(job.created_at))

    def _build_job_url(self, job: JobDescription) -> str:
        return build_public_job_url(job)

    def _build_apply_url(self, job: JobDescription) -> str:
        return build_public_apply_url(job)

    @staticmethod
    def _render_skills(skills) -> str:
        return ", ".join(normalize_skills(skills))
