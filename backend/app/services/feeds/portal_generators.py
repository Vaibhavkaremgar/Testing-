from xml.etree import ElementTree as ET

from app.models import JobDescription
from app.services.feeds.base import BaseFeedGenerator
from app.utils.xml_utils import append_text_element, format_datetime


class JoobleFeedGenerator(BaseFeedGenerator):
    portal_name = "jooble"


class CareerJetFeedGenerator(BaseFeedGenerator):
    portal_name = "careerjet"

    def populate_job_node(self, parent: ET.Element, job: JobDescription) -> None:
        super().populate_job_node(parent, job)
        append_text_element(parent, "reference", job.job_id or str(job.id))


class TalentFeedGenerator(BaseFeedGenerator):
    portal_name = "talent"
    item_tag = "position"

    def populate_job_node(self, parent: ET.Element, job: JobDescription) -> None:
        append_text_element(parent, "uuid", job.id)
        append_text_element(parent, "title", job.title)
        append_text_element(parent, "company", job.company_name)
        append_text_element(parent, "summary", job.description)
        append_text_element(parent, "skills", self._render_skills(job.skills))
        append_text_element(parent, "location", job.location)
        append_text_element(parent, "employment_type", job.employment_type)
        append_text_element(parent, "experience", job.experience_required)
        append_text_element(parent, "salary", job.salary_range)
        append_text_element(parent, "job_url", self._build_job_url(job))
        append_text_element(parent, "created_at", format_datetime(job.created_at))
