import pytest

from netpulse.checks.validation import normalize_host


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.0.2.10", "192.0.2.10"),
        ("2001:db8::1", "2001:db8::1"),
        ("Example.COM", "example.com"),
        ("printer.local.", "printer.local"),
        ("münchen.example", "xn--mnchen-3ya.example"),
    ],
)
def test_normalize_host_accepts_addresses_and_hostnames(value: str, expected: str) -> None:
    assert normalize_host(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "bad host", "-option.example", "host;whoami", "host|command", "../host"],
)
def test_normalize_host_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_host(value)
