from app.core.configuration import Settings


def test_allowed_origins_strip_paths_and_trailing_slashes():
    settings = Settings(
        DEBUG=False,
        FRONTEND_URL="https://efficient-curiosity-production-a012.up.railway.app/api/",
        ALLOWED_ORIGINS=(
            "https://dashboard.pontis.one/,"
            "https://testing-production-0d3c.up.railway.app/api,"
            "http://localhost:5173/"
        ),
    )

    assert "https://efficient-curiosity-production-a012.up.railway.app" in settings.allowed_origins_list
    assert "https://testing-production-0d3c.up.railway.app" in settings.allowed_origins_list
    assert "http://localhost:5173" in settings.allowed_origins_list
    assert all("/api" not in origin for origin in settings.allowed_origins_list)
