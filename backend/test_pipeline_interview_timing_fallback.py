from datetime import date, datetime, timedelta, timezone
import uuid

from app.routes.candidates import (
    _classify_interview_timing_bucket,
    _get_interview_candidate_ids_by_interview_timing,
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
