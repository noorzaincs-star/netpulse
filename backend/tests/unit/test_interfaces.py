from types import SimpleNamespace

from netpulse.services.interfaces import InterfaceSampler


def test_interface_sampler_reports_host_rates_and_counter_resets(
    monkeypatch,
) -> None:
    counters = iter(
        [
            {"Ethernet": SimpleNamespace(bytes_sent=100, bytes_recv=200)},
            {"Ethernet": SimpleNamespace(bytes_sent=300, bytes_recv=600)},
            {"Ethernet": SimpleNamespace(bytes_sent=50, bytes_recv=75)},
        ]
    )
    clocks = iter([1.0, 3.0, 4.0])
    monkeypatch.setattr(
        "netpulse.services.interfaces.psutil.net_io_counters",
        lambda pernic: next(counters),
    )
    monkeypatch.setattr(
        "netpulse.services.interfaces.psutil.net_if_stats",
        lambda: {"Ethernet": SimpleNamespace(isup=True, speed=1000, mtu=1500)},
    )
    monkeypatch.setattr(
        "netpulse.services.interfaces.time.monotonic",
        lambda: next(clocks),
    )

    sampler = InterfaceSampler()
    initial = sampler.snapshot()["interfaces"][0]
    measured = sampler.snapshot()["interfaces"][0]
    reset = sampler.snapshot()["interfaces"][0]

    assert initial["rate_available"] is False
    assert measured["bytes_sent_per_second"] == 100
    assert measured["bytes_received_per_second"] == 200
    assert measured["rate_available"] is True
    assert reset["counter_reset"] is True
    assert reset["rate_available"] is False
