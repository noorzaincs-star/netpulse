import pytest

from netpulse.core.config import Settings


@pytest.mark.parametrize(
    "values",
    [
        {"max_concurrency": 0},
        {"failure_threshold": 0},
        {"recovery_threshold": 101},
        {"packet_loss_threshold_percent": 101},
        {"measurement_retention_days": 0},
        {"cors_origins": ("https://example.com/path",)},
    ],
)
def test_settings_reject_unsafe_or_unbounded_values(values: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Settings(**values)


def test_settings_accept_local_frontend_origins() -> None:
    settings = Settings(
        cors_origins=("http://localhost:5173", "http://127.0.0.1:5173")
    )

    assert len(settings.cors_origins) == 2


def test_settings_accept_deployment_origins() -> None:
    settings = Settings(
        cors_origins=("https://netpulse.vercel.app",),
        allowed_hosts=("localhost", "netpulse-api.onrender.com"),
    )

    assert settings.cors_origins == ("https://netpulse.vercel.app",)
    assert "netpulse-api.onrender.com" in settings.allowed_hosts


def test_environment_reads_deployment_cors_and_render_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://netpulse.vercel.app,https://preview.vercel.app")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "netpulse-api.onrender.com")

    settings = Settings.from_environment()

    assert settings.cors_origins == (
        "https://netpulse.vercel.app",
        "https://preview.vercel.app",
    )
    assert "netpulse-api.onrender.com" in settings.allowed_hosts
