from types import SimpleNamespace
from uuid import uuid4


import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.routes import interviews as interviews_route


def override_get_db():
    yield object()


app.dependency_overrides[get_db] = override_get_db


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursor()

    def close(self):
        return None


class FakeUpstreamResponse:
    def __init__(self, status_code=200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []
        self.closed = False

    def iter_content(self, chunk_size=1):
        for chunk in self._chunks:
            yield chunk

    def close(self):
        self.closed = True


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(interviews_route.psycopg2, "connect", lambda *args, **kwargs: FakeConnection())
    monkeypatch.setattr(interviews_route, "normalize_legacy_candidate_stages", lambda db: None)
    original_startup = list(app.router.on_startup)
    original_shutdown = list(app.router.on_shutdown)
    app.router.on_startup = []
    app.router.on_shutdown = []
    with TestClient(app) as c:
        yield c
    app.router.on_startup = original_startup
    app.router.on_shutdown = original_shutdown


def test_recording_proxy_streams_range_requests_for_authorized_user(client, monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    interview = SimpleNamespace(id=uuid4(), async_token="async-session-token")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_SERVICE_TOKEN", "recording-secret")
    monkeypatch.setattr(interviews_route.settings, "INTERNAL_SERVICE_TOKEN", "")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_BASE_URL", "https://interview.pontis.one")

    monkeypatch.setattr(interviews_route, "_resolve_video_request_user", lambda db, access_token, user: current_user)
    monkeypatch.setattr(
        interviews_route,
        "_fetch_interview_session_row_by_session_token",
        lambda cursor, session_token: {
            "session_token": session_token,
            "interview_id": str(interview.id),
            "async_token": interview.async_token,
        },
    )
    monkeypatch.setattr(
        interviews_route,
        "_resolve_scoped_interview_from_session_row",
        lambda db, session_row, user: interview,
    )

    def fake_request(method, url, headers=None, params=None, stream=None, timeout=None):
        assert method == "GET"
        assert url == "https://interview.pontis.one/api/recording"
        assert params == {"session_token": "session-123"}
        assert headers == {
            "Authorization": "Bearer recording-secret",
            "Range": "bytes=0-1023",
        }
        assert stream is True
        return FakeUpstreamResponse(
            status_code=206,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": "1024",
                "Content-Range": "bytes 0-1023/4096",
                "Content-Type": "video/mp4",
            },
            chunks=[b"a" * 512, b"b" * 512],
        )

    monkeypatch.setattr(interviews_route.requests, "request", fake_request)

    response = client.get("/api/recording/session-123", headers={"Range": "bytes=0-1023"})

    assert response.status_code == 206
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == "bytes 0-1023/4096"
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == (b"a" * 512 + b"b" * 512)


def test_recording_proxy_supports_head_requests_for_player_validation(client, monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    interview = SimpleNamespace(id=uuid4(), async_token="async-session-token")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_SERVICE_TOKEN", "recording-secret")
    monkeypatch.setattr(interviews_route.settings, "INTERNAL_SERVICE_TOKEN", "")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_BASE_URL", "https://interview.pontis.one")

    monkeypatch.setattr(interviews_route, "_resolve_video_request_user", lambda db, access_token, user: current_user)
    monkeypatch.setattr(
        interviews_route,
        "_fetch_interview_session_row_by_session_token",
        lambda cursor, session_token: {
            "session_token": session_token,
            "interview_id": str(interview.id),
            "async_token": interview.async_token,
        },
    )
    monkeypatch.setattr(
        interviews_route,
        "_resolve_scoped_interview_from_session_row",
        lambda db, session_row, user: interview,
    )

    def fake_request(method, url, headers=None, params=None, stream=None, timeout=None):
        assert method == "HEAD"
        assert url == "https://interview.pontis.one/api/recording"
        assert params == {"session_token": "session-webm"}
        assert headers == {"Authorization": "Bearer recording-secret"}
        return FakeUpstreamResponse(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": "4096",
                "Content-Type": "video/webm",
            },
        )

    monkeypatch.setattr(interviews_route.requests, "request", fake_request)

    response = client.head("/api/recording/session-webm")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "4096"
    assert response.headers["content-type"] == "video/webm"
    assert response.content == b""


def test_recording_proxy_normalizes_session_token_extensions(client, monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    interview = SimpleNamespace(id=uuid4(), async_token="async-session-token")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_SERVICE_TOKEN", "recording-secret")
    monkeypatch.setattr(interviews_route.settings, "INTERNAL_SERVICE_TOKEN", "")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_BASE_URL", "https://interview.pontis.one")

    monkeypatch.setattr(interviews_route, "_resolve_video_request_user", lambda db, access_token, user: current_user)

    def fake_fetch_session(cursor, session_token):
        assert session_token == "session-normalized"
        return {
            "session_token": session_token,
            "interview_id": str(interview.id),
            "async_token": interview.async_token,
        }

    monkeypatch.setattr(
        interviews_route,
        "_fetch_interview_session_row_by_session_token",
        fake_fetch_session,
    )
    monkeypatch.setattr(
        interviews_route,
        "_resolve_scoped_interview_from_session_row",
        lambda db, session_row, user: interview,
    )

    def fake_request(method, url, headers=None, params=None, stream=None, timeout=None):
        assert method == "GET"
        assert url == "https://interview.pontis.one/api/recording"
        assert params == {"session_token": "session-normalized"}
        assert headers == {"Authorization": "Bearer recording-secret"}
        assert stream is True
        return FakeUpstreamResponse(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": "10",
                "Content-Type": "video/mp4",
            },
            chunks=[b"normalized"],
        )

    monkeypatch.setattr(interviews_route.requests, "request", fake_request)

    response = client.get("/api/recording/session-normalized.webm")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == b"normalized"


def test_recording_proxy_directly_resolves_uuid_shaped_async_token(client, monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    session_token = "3b0d9bba-6487-421c-8d9d-8629ecfb5e0d"
    interview = SimpleNamespace(id=uuid4(), async_token=session_token)
    monkeypatch.setattr(interviews_route.settings, "RECORDING_SERVICE_TOKEN", "recording-secret")
    monkeypatch.setattr(interviews_route.settings, "INTERNAL_SERVICE_TOKEN", "")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_BASE_URL", "https://interview.pontis.one")

    monkeypatch.setattr(interviews_route, "_resolve_video_request_user", lambda db, access_token, user: current_user)
    monkeypatch.setattr(
        interviews_route,
        "_get_scoped_interview_for_video",
        lambda db, lookup_key, user: interview if lookup_key == session_token else None,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("interview_sessions lookup should not be required for direct async_token matches")

    monkeypatch.setattr(interviews_route.psycopg2, "connect", fail_if_called)

    def fake_request(method, url, headers=None, params=None, stream=None, timeout=None):
        assert method == "GET"
        assert url == "https://interview.pontis.one/api/recording"
        assert params == {"session_token": session_token}
        assert headers == {"Authorization": "Bearer recording-secret"}
        assert stream is True
        return FakeUpstreamResponse(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": "4",
                "Content-Type": "video/webm",
            },
            chunks=[b"uuid"],
        )

    monkeypatch.setattr(interviews_route.requests, "request", fake_request)

    response = client.get(f"/api/recording/{session_token}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/webm")
    assert response.content == b"uuid"


def test_recording_proxy_requires_authentication(client):
    response = client.get("/api/recording/session-123")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required to access interview recordings"


def test_recording_proxy_blocks_cross_agency_access(client, monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(interviews_route.settings, "RECORDING_BASE_URL", "https://interview.pontis.one")

    monkeypatch.setattr(interviews_route, "_resolve_video_request_user", lambda db, access_token, user: current_user)
    monkeypatch.setattr(
        interviews_route,
        "_fetch_interview_session_row_by_session_token",
        lambda cursor, session_token: {
            "session_token": session_token,
            "interview_id": str(uuid4()),
            "async_token": "out-of-scope-token",
        },
    )
    monkeypatch.setattr(
        interviews_route,
        "_resolve_scoped_interview_from_session_row",
        lambda db, session_row, user: None,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Upstream recording service should not be called for denied access")

    monkeypatch.setattr(interviews_route.requests, "request", fail_if_called)

    response = client.get("/api/recording/session-123")

    assert response.status_code == 404
    assert response.json()["detail"] == "Interview recording not found"


def test_interview_video_endpoint_proxies_by_interview_id(client, monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    interview = SimpleNamespace(id=uuid4(), async_token="async-session-token.webm")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_SERVICE_TOKEN", "recording-secret")
    monkeypatch.setattr(interviews_route.settings, "INTERNAL_SERVICE_TOKEN", "")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_BASE_URL", "https://interview.pontis.one")

    monkeypatch.setattr(interviews_route, "_resolve_video_request_user", lambda db, access_token, user: current_user)
    monkeypatch.setattr(
        interviews_route,
        "_get_scoped_interview_for_video",
        lambda db, session_id, user: interview,
    )

    def fake_request(method, url, headers=None, params=None, stream=None, timeout=None):
        assert method == "GET"
        assert url == "https://interview.pontis.one/api/recording"
        assert params == {"session_token": "async-session-token"}
        assert headers == {"Authorization": "Bearer recording-secret"}
        return FakeUpstreamResponse(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": "8",
                "Content-Type": "video/mp4",
            },
            chunks=[b"proxy-ok"],
        )

    monkeypatch.setattr(interviews_route.requests, "request", fake_request)

    response = client.get(f"/api/interviews/video/{interview.id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == b"proxy-ok"


def test_recording_proxy_uses_internal_service_token_when_recording_service_token_is_missing(client, monkeypatch):
    current_user = SimpleNamespace(id=uuid4())
    interview = SimpleNamespace(id=uuid4(), async_token="async-session-token")
    monkeypatch.setattr(interviews_route.settings, "INTERNAL_SERVICE_TOKEN", "internal-secret")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_SERVICE_TOKEN", "")
    monkeypatch.setattr(interviews_route.settings, "RECORDING_BASE_URL", "https://interview.pontis.one")

    monkeypatch.setattr(interviews_route, "_resolve_video_request_user", lambda db, access_token, user: current_user)
    monkeypatch.setattr(
        interviews_route,
        "_fetch_interview_session_row_by_session_token",
        lambda cursor, session_token: {
            "session_token": session_token,
            "interview_id": str(interview.id),
            "async_token": interview.async_token,
        },
    )
    monkeypatch.setattr(
        interviews_route,
        "_resolve_scoped_interview_from_session_row",
        lambda db, session_row, user: interview,
    )

    def fake_request(method, url, headers=None, params=None, stream=None, timeout=None):
        assert url == "https://interview.pontis.one/api/recording"
        assert params == {"session_token": "session-fallback"}
        assert headers == {"Authorization": "Bearer internal-secret"}
        return FakeUpstreamResponse(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": "8",
                "Content-Type": "video/webm",
            },
            chunks=[b"fallback"],
        )

    monkeypatch.setattr(interviews_route.requests, "request", fake_request)

    response = client.get("/api/recording/session-fallback")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/webm")
    assert response.content == b"fallback"
