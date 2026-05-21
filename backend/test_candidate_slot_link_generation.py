import uuid

from app.models import Candidate
from app.routes.candidates import _build_candidate_slot_booking_link


class _FakeDb:
    pass


def test_build_candidate_slot_booking_link_prefers_workflow_slot_link(monkeypatch):
    candidate = Candidate(id=uuid.uuid4(), name="Test Candidate")

    def _fake_build_rendered_notification(db, *, candidate, status, user_id=None, extra_payload=None):
        assert status == "slot_selection"
        return {
            "payload": {
                "slot_link": "https://booking.example.com/slot-selection?token=abc123",
            }
        }

    monkeypatch.setattr(
        "app.routes.notifications.build_rendered_notification",
        _fake_build_rendered_notification,
    )

    link = _build_candidate_slot_booking_link(_FakeDb(), candidate, user_id=uuid.uuid4())

    assert link == "https://booking.example.com/slot-selection?token=abc123"
