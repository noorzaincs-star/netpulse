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
        {"cors_origins": ("https://untrusted.example",)},
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
