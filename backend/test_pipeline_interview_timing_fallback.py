from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import sys
import uuid

from app.models import Candidate, CandidateStage, Interview
from app.schemas import InterviewCreate, InterviewUpdate
from app.routes.candidates import (
    _classify_interview_timing_bucket,
    _get_effective_interview_scheduled_at_utc,
    _get_india_now,
    get_pipeline_stages,
    _get_slot_no_show_cutoff_ist,
    _get_interview_candidate_ids_by_interview_timing,
    _normalize_interview_status_value,
    sync_no_show_candidate_stages,
    sync_rescheduled_candidate_stages_from_slots,
)
from app.routes.interviews import (
    _derive_candidate_stage_from_interview,
    _normalize_interview_scheduled_at_for_storage,
)

candidates_route = sys.modules["app.routes.candidates"]


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


class _RoutingFakeDb:
    def __init__(self, rows_by_arity):
        self._rows_by_arity = rows_by_arity

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows_by_arity.get(len(args), []))


class _FakeCandidateQuery:
    def __init__(self, candidates):
        self._candidates = candidates

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._candidates


class _FakeCandidateDb:
    def __init__(self, candidates):
        self._candidates = candidates
        self.commit_calls = 0

    def query(self, *args, **kwargs):
        return _FakeCandidateQuery(self._candidates)

    def execute(self, *args, **kwargs):
        return _FakeExecuteResult([])

    def commit(self):
        self.commit_calls += 1


class _FakePipelineQuery:
    def __init__(self, candidates):
        self._candidates = candidates

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._candidates


class _FakePipelineDb:
    def __init__(self, candidates):
        self._candidates = candidates

    def query(self, *args, **kwargs):
        return _FakePipelineQuery(self._candidates)


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeNoShowQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeNoShowDb:
    def __init__(
        self,
        *,
        interviews,
        stage_candidate_ids,
        slot_lookup_rows,
        candidates,
        slot_columns=None,
        slot_rows=None,
    ):
        self._interviews = interviews
        self._stage_candidate_ids = stage_candidate_ids
        self._slot_lookup_rows = slot_lookup_rows
        self._candidates = candidates
        self._slot_columns = slot_columns or []
        self._slot_rows = slot_rows or []
        self.commit_calls = 0

    def query(self, *args, **kwargs):
        if len(args) == 1 and args[0] is Interview:
            return _FakeNoShowQuery(self._interviews)
        if len(args) == 1 and getattr(args[0], "key", None) == "id":
            return _FakeNoShowQuery(self._stage_candidate_ids)
        if (
            len(args) == 2
            and getattr(args[0], "key", None) == "id"
            and getattr(args[1], "key", None) == "candidate_id"
        ):
            return _FakeNoShowQuery(self._slot_lookup_rows)
        if len(args) == 1 and args[0] is Candidate:
            return _FakeNoShowQuery(self._candidates)
        raise AssertionError(f"Unexpected query args: {args}")

    def execute(self, *args, **kwargs):
        statement = args[0] if args else ""
        sql = str(statement)
        if "information_schema.columns" in sql:
            return _FakeExecuteResult([(column_name,) for column_name in self._slot_columns])
        if "FROM interview_slots" in sql:
            return _FakeExecuteResult(self._slot_rows)
        return _FakeExecuteResult([])

    def commit(self):
        self.commit_calls += 1


class _FakeSessionSlotDb:
    def __init__(self, *, slot_columns, slot_session_rows, candidate_lookup_rows=None, interview_rows=None):
        self._slot_columns = slot_columns
        self._slot_session_rows = slot_session_rows
        self._candidate_lookup_rows = candidate_lookup_rows or []
        self._interview_rows = interview_rows or []

    def query(self, *args, **kwargs):
        if len(args) == 2:
            return _FakeQuery(self._candidate_lookup_rows)
        if len(args) == 4:
            return _FakeQuery(self._interview_rows)
        raise AssertionError(f"Unexpected query args: {args}")

    def execute(self, statement, params=None):
        sql = str(statement)
        if "information_schema.columns" in sql:
            return _FakeExecuteResult([(column_name,) for column_name in self._slot_columns])
        if "FROM interview_slots" in sql:
            return _FakeExecuteResult([])
        if "FROM interview_sessions s" in sql:
            return _FakeExecuteResult(self._slot_session_rows)
        raise AssertionError(f"Unexpected execute SQL: {sql}")


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


def test_classify_interview_timing_bucket_marks_later_today_interviews_as_today():
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
        == "today"
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
    db = _RoutingFakeDb({
        2: [],
        4: rows,
    })

    today_ids, future_ids = _get_interview_candidate_ids_by_interview_timing(
        db,
        [candidate_id, other_candidate_id],
        today,
    )

    assert candidate_id in future_ids
    assert candidate_id not in today_ids
    assert other_candidate_id in today_ids


def test_normalize_interview_status_value_maps_no_show_variants():
    assert _normalize_interview_status_value("No Show") == "no_show"
    assert _normalize_interview_status_value("no-show") == "no_show"
    assert _normalize_interview_status_value("in_progress") == "ongoing"


def test_get_interview_candidate_ids_by_interview_timing_uses_linked_candidate_interviews_for_stage_recovery():
    today = date(2026, 5, 14)
    original_candidate_id = uuid.uuid4()
    linked_candidate_id = uuid.uuid4()
    db = _RoutingFakeDb({
        2: [
            (original_candidate_id, "ORIGINAL-CODE"),
            (linked_candidate_id, str(original_candidate_id)),
        ],
        4: [
            (
                linked_candidate_id,
                "scheduled",
                datetime(2026, 5, 15, 11, 0, tzinfo=timezone.utc),
                datetime(2026, 5, 14, 8, 21, tzinfo=timezone.utc),
            ),
        ],
    })

    today_ids, future_ids = _get_interview_candidate_ids_by_interview_timing(
        db,
        [original_candidate_id],
        today,
    )

    assert original_candidate_id in future_ids
    assert original_candidate_id not in today_ids


def test_get_interview_slot_candidate_ids_by_timing_uses_booked_interview_sessions_before_interview_fallback():
    today = date(2026, 5, 14)
    candidate_id = uuid.uuid4()
    db = _FakeSessionSlotDb(
        slot_columns=["slot_date", "slot_time", "candidate_id"],
        slot_session_rows=[
            {
                "candidate_id": str(candidate_id),
                "slot_date": date(2026, 5, 15),
                "slot_time": None,
                "booked_at": datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
            },
        ],
        candidate_lookup_rows=[(candidate_id, None)],
        interview_rows=[],
    )

    today_ids, future_ids = candidates_route._get_interview_slot_candidate_ids_by_timing(
        db,
        [candidate_id],
        today,
    )

    assert candidate_id in future_ids
    assert candidate_id not in today_ids


def test_get_slot_no_show_cutoff_ist_applies_thirty_minute_grace_period():
    now_utc = datetime(2026, 5, 12, 6, 0, tzinfo=timezone.utc)

    cutoff_ist = _get_slot_no_show_cutoff_ist(now_utc)

    assert cutoff_ist == datetime(2026, 5, 12, 11, 0)


def test_derive_candidate_stage_from_interview_marks_same_day_scheduled_interviews_as_interviewed():
    india_now = _get_india_now()
    scheduled_local = india_now + timedelta(hours=1)
    interview = Interview(
        candidate_id=uuid.uuid4(),
        status="scheduled",
        scheduled_at=scheduled_local.replace(second=0, microsecond=0).astimezone(timezone.utc),
    )

    assert _derive_candidate_stage_from_interview(interview) == CandidateStage.INTERVIEWED


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


def test_sync_rescheduled_candidate_stages_from_slots_moves_future_slots_to_scheduled(monkeypatch):
    candidate = Candidate(id=uuid.uuid4(), stage=CandidateStage.INTERVIEW_RESCHEDULED)
    db = _FakeCandidateDb([candidate])

    monkeypatch.setattr(candidates_route, "_get_india_today", lambda: date(2026, 5, 15))
    monkeypatch.setattr(
        candidates_route,
        "_get_interview_session_slot_stage_by_candidate",
        lambda _db, _candidate_ids, _today, _candidate_by_id: {candidate.id: CandidateStage.INTERVIEW_SCHEDULED},
    )
    monkeypatch.setattr(
        candidates_route,
        "_get_rescheduled_candidate_stage_from_interviews",
        lambda _db, _candidate_ids, _today, _candidate_by_id: {},
    )

    updated_count = sync_rescheduled_candidate_stages_from_slots(db)

    assert updated_count == 1
    assert candidate.stage == CandidateStage.INTERVIEW_SCHEDULED
    assert candidate.stage_updated_at is not None
    assert candidate.stage_entered_at is not None
    assert db.commit_calls == 1


def test_sync_rescheduled_candidate_stages_from_slots_moves_same_day_slots_to_interviewed(monkeypatch):
    candidate = Candidate(id=uuid.uuid4(), stage=CandidateStage.INTERVIEW_RESCHEDULED)
    db = _FakeCandidateDb([candidate])

    monkeypatch.setattr(candidates_route, "_get_india_today", lambda: date(2026, 5, 15))
    monkeypatch.setattr(
        candidates_route,
        "_get_interview_session_slot_stage_by_candidate",
        lambda _db, _candidate_ids, _today, _candidate_by_id: {candidate.id: CandidateStage.INTERVIEWED},
    )
    monkeypatch.setattr(
        candidates_route,
        "_get_rescheduled_candidate_stage_from_interviews",
        lambda _db, _candidate_ids, _today, _candidate_by_id: {},
    )

    updated_count = sync_rescheduled_candidate_stages_from_slots(db)

    assert updated_count == 1
    assert candidate.stage == CandidateStage.INTERVIEWED
    assert db.commit_calls == 1


def test_sync_rescheduled_candidate_stages_from_slots_keeps_rescheduled_when_no_valid_slot_stage(monkeypatch):
    candidate = Candidate(id=uuid.uuid4(), stage=CandidateStage.INTERVIEW_RESCHEDULED)
    db = _FakeCandidateDb([candidate])

    monkeypatch.setattr(candidates_route, "_get_india_today", lambda: date(2026, 5, 15))
    monkeypatch.setattr(
        candidates_route,
        "_get_interview_session_slot_stage_by_candidate",
        lambda _db, _candidate_ids, _today, _candidate_by_id: {},
    )
    monkeypatch.setattr(
        candidates_route,
        "_get_rescheduled_candidate_stage_from_interviews",
        lambda _db, _candidate_ids, _today, _candidate_by_id: {},
    )

    updated_count = sync_rescheduled_candidate_stages_from_slots(db)

    assert updated_count == 0
    assert candidate.stage == CandidateStage.INTERVIEW_RESCHEDULED
    assert db.commit_calls == 0


def test_sync_no_show_candidate_stages_marks_missed_rescheduled_interviews_as_no_show(monkeypatch):
    frozen_now_utc = datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen_now_utc.replace(tzinfo=None)
            return frozen_now_utc.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return frozen_now_utc.replace(tzinfo=None)

    candidate = Candidate(id=uuid.uuid4(), stage=CandidateStage.INTERVIEW_RESCHEDULED)
    interview = Interview(
        candidate_id=candidate.id,
        status="rescheduled",
        scheduled_at=datetime(2026, 5, 15, 6, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 15, 5, 0, tzinfo=timezone.utc),
    )
    db = _FakeNoShowDb(
        interviews=[interview],
        stage_candidate_ids=[(candidate.id,)],
        slot_lookup_rows=[(candidate.id, None)],
        candidates=[candidate],
    )

    monkeypatch.setattr(candidates_route, "datetime", _FrozenDateTime)

    updated_count = sync_no_show_candidate_stages(db)

    assert updated_count == 1
    assert candidate.stage == CandidateStage.NO_SHOW
    assert interview.status == "no_show"
    assert db.commit_calls == 1


def test_sync_no_show_candidate_stages_marks_missed_same_day_slot_candidates_as_no_show(monkeypatch):
    frozen_now_utc = datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen_now_utc.replace(tzinfo=None)
            return frozen_now_utc.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return frozen_now_utc.replace(tzinfo=None)

    candidate = Candidate(id=uuid.uuid4(), stage=CandidateStage.INTERVIEWED)
    db = _FakeNoShowDb(
        interviews=[],
        stage_candidate_ids=[(candidate.id,)],
        slot_lookup_rows=[(candidate.id, None)],
        candidates=[candidate],
        slot_columns=["candidate_id", "slot_date", "slot_time"],
        slot_rows=[
            {
                "candidate_id": str(candidate.id).lower(),
                "slot_date": date(2026, 5, 15),
                "slot_time": datetime(2026, 5, 15, 12, 0).time(),
            }
        ],
    )

    monkeypatch.setattr(candidates_route, "datetime", _FrozenDateTime)

    updated_count = sync_no_show_candidate_stages(db)

    assert updated_count == 1
    assert candidate.stage == CandidateStage.NO_SHOW
    assert db.commit_calls == 1


def test_sync_no_show_candidate_stages_corrects_false_selected_status_for_missed_interview(monkeypatch):
    frozen_now_utc = datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen_now_utc.replace(tzinfo=None)
            return frozen_now_utc.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return frozen_now_utc.replace(tzinfo=None)

    candidate = Candidate(id=uuid.uuid4(), stage=CandidateStage.INTERVIEWED)
    interview = Interview(
        candidate_id=candidate.id,
        status="selected",
        scheduled_at=datetime(2026, 5, 15, 6, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 15, 5, 0, tzinfo=timezone.utc),
    )
    db = _FakeNoShowDb(
        interviews=[interview],
        stage_candidate_ids=[(candidate.id,)],
        slot_lookup_rows=[(candidate.id, None)],
        candidates=[candidate],
    )

    monkeypatch.setattr(candidates_route, "datetime", _FrozenDateTime)

    updated_count = sync_no_show_candidate_stages(db)

    assert updated_count == 1
    assert candidate.stage == CandidateStage.NO_SHOW
    assert interview.status == "no_show"
    assert db.commit_calls == 1


def test_sync_no_show_candidate_stages_marks_selected_stage_slot_candidate_as_no_show(monkeypatch):
    frozen_now_utc = datetime(2026, 5, 15, 8, 0, tzinfo=timezone.utc)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen_now_utc.replace(tzinfo=None)
            return frozen_now_utc.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return frozen_now_utc.replace(tzinfo=None)

    candidate = Candidate(id=uuid.uuid4(), stage=CandidateStage.SELECTED)
    db = _FakeNoShowDb(
        interviews=[],
        stage_candidate_ids=[(candidate.id,)],
        slot_lookup_rows=[(candidate.id, None)],
        candidates=[candidate],
        slot_columns=["candidate_id", "slot_date", "slot_time"],
        slot_rows=[
            {
                "candidate_id": str(candidate.id).lower(),
                "slot_date": date(2026, 5, 15),
                "slot_time": datetime(2026, 5, 15, 12, 0).time(),
            }
        ],
    )

    monkeypatch.setattr(candidates_route, "datetime", _FrozenDateTime)

    updated_count = sync_no_show_candidate_stages(db)

    assert updated_count == 1
    assert candidate.stage == CandidateStage.NO_SHOW
    assert db.commit_calls == 1


def test_get_pipeline_stages_does_not_use_candidate_stage_for_interview_columns(monkeypatch):
    candidate = Candidate(
        id=uuid.uuid4(),
        name="Slotless Candidate",
        stage=CandidateStage.INTERVIEWED,
        current_role="Engineer",
        current_company="Acme",
        resume_score=88,
    )
    db = _FakePipelineDb([candidate])
    current_user = SimpleNamespace(role="admin")

    monkeypatch.setattr(candidates_route, "normalize_legacy_candidate_stages", lambda _db: None)
    monkeypatch.setattr(candidates_route, "sync_active_rescheduled_candidate_stages", lambda _db: 0)
    monkeypatch.setattr(candidates_route, "sync_no_show_candidate_stages", lambda _db: 0)
    monkeypatch.setattr(candidates_route, "sync_rescheduled_candidate_stages_from_slots", lambda _db: 0)
    monkeypatch.setattr(candidates_route, "_apply_candidate_list_scope", lambda query, _current_user: query)
    monkeypatch.setattr(candidates_route, "_apply_client_filter", lambda query, _client: query)
    monkeypatch.setattr(candidates_route, "_get_india_today", lambda: date(2026, 5, 15))
    monkeypatch.setattr(
        candidates_route,
        "_get_interview_slot_candidate_ids_by_timing",
        lambda _db, _candidate_ids, _today: (set(), set()),
    )
    monkeypatch.setattr(
        candidates_route,
        "_get_interview_candidate_ids_by_status",
        lambda _db, _candidate_ids: (set(), set(), set()),
    )

    stages = get_pipeline_stages(
        client=None,
        job_id=None,
        agency_id=None,
        db=db,
        current_user=current_user,
    )

    assert stages["INTERVIEWED"] == []
