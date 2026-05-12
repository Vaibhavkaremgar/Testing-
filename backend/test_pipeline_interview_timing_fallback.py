from datetime import date, datetime, timedelta, timezone
import uuid

from app.models import CandidateStage, Interview
from app.schemas import InterviewCreate, InterviewUpdate
from app.routes.candidates import (
    _classify_interview_timing_bucket,
    _get_effective_interview_scheduled_at_utc,
    _get_india_now,
    _get_slot_no_show_cutoff_ist,
    _get_interview_candidate_ids_by_interview_timing,
)
from app.routes.interviews import (
    _derive_candidate_stage_from_interview,
    _normalize_interview_scheduled_at_for_storage,
)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)


def test_classify_interview_timing_bucket_marks_future_scheduled_interviews():
    today = date(2026, 5, 10)
    scheduled_at = datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc)

    assert (
        _classify_interview_timing_bucket(
            status_value="scheduled",
            scheduled_at=scheduled_at,
            today=today,
        )
        == "future"
    )


def test_classify_interview_timing_bucket_keeps_later_today_interviews_in_future_bucket():
    now_utc = datetime(2026, 5, 12, 6, 19, tzinfo=timezone.utc)
    today = _get_india_now(now_utc).date()
    scheduled_at = datetime(2026, 5, 12, 11, 0, tzinfo=timezone.utc)

    assert (
        _classify_interview_timing_bucket(
            status_value="scheduled",
            scheduled_at=scheduled_at,
            today=today,
            now_utc=now_utc,
        )
        == "future"
    )


def test_get_interview_candidate_ids_by_interview_timing_uses_latest_interview_per_candidate():
    today = date(2026, 5, 10)
    candidate_id = uuid.uuid4()
    other_candidate_id = uuid.uuid4()
    rows = [
        (
            candidate_id,
            "scheduled",
            datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc),
        ),
        (
            candidate_id,
            "completed",
            datetime(2026, 5, 9, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc),
        ),
        (
            other_candidate_id,
            "completed",
            datetime(2026, 5, 10, 7, 0, tzinfo=timezone.utc) - timedelta(hours=1),
            datetime(2026, 5, 10, 7, 0, tzinfo=timezone.utc),
        ),
    ]
    db = _FakeDb(rows)

    today_ids, future_ids = _get_interview_candidate_ids_by_interview_timing(
        db,
        [candidate_id, other_candidate_id],
        today,
    )

    assert candidate_id in future_ids
    assert candidate_id not in today_ids
    assert other_candidate_id in today_ids


def test_get_slot_no_show_cutoff_ist_applies_thirty_minute_grace_period():
    now_utc = datetime(2026, 5, 12, 6, 0, tzinfo=timezone.utc)

    cutoff_ist = _get_slot_no_show_cutoff_ist(now_utc)

    assert cutoff_ist == datetime(2026, 5, 12, 11, 0)


def test_derive_candidate_stage_from_interview_keeps_later_today_scheduled_interviews_in_scheduled_stage():
    interview = Interview(
        candidate_id=uuid.uuid4(),
        status="scheduled",
        scheduled_at=datetime(2099, 5, 12, 11, 0, tzinfo=timezone.utc),
    )

    assert _derive_candidate_stage_from_interview(interview) == CandidateStage.INTERVIEW_SCHEDULED


def test_normalize_interview_scheduled_at_for_storage_treats_naive_values_as_ist():
    normalized = _normalize_interview_scheduled_at_for_storage(datetime(2026, 5, 12, 11, 0))

    assert normalized == datetime(2026, 5, 12, 5, 30, tzinfo=timezone.utc)


def test_interview_create_schema_treats_naive_scheduled_at_as_ist():
    payload = InterviewCreate(
        candidate_id=uuid.uuid4(),
        scheduled_at="2026-05-12T11:00:00",
    )

    assert payload.scheduled_at == datetime(2026, 5, 12, 11, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def test_interview_update_schema_treats_naive_scheduled_at_as_ist():
    payload = InterviewUpdate(scheduled_at="2026-05-12T11:00:00")

    assert payload.scheduled_at == datetime(2026, 5, 12, 11, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def test_effective_interview_scheduled_at_utc_reinterprets_legacy_session_links_as_ist():
    interview = Interview(
        candidate_id=uuid.uuid4(),
        status="scheduled",
        scheduled_at=datetime(2026, 5, 12, 11, 0, tzinfo=timezone.utc),
        async_link="https://pontis-backend-production.up.railway.app/interview?session=test",
        meeting_link=None,
        is_async=False,
    )

    assert _get_effective_interview_scheduled_at_utc(interview) == datetime(2026, 5, 12, 5, 30, tzinfo=timezone.utc)
