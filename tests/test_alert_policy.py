from app.domain import Signal
from app.services.alert_policy import AlertPolicy


class FakeRepo:
    def __init__(self, in_cooldown: bool) -> None:
        self.in_cooldown = in_cooldown

    async def is_in_cooldown(self, fingerprint: str, minutes: int) -> bool:
        return self.in_cooldown


async def test_alert_policy_sends_eligible_signal() -> None:
    signal = Signal("OI_ANOMALY", 80, "HIGH", 0.9, {})
    decision = await AlertPolicy(30).decide(FakeRepo(False), "LABUSDT:OI_ANOMALY", signal)
    assert decision.action == "send"


async def test_alert_policy_suppresses_cooldown() -> None:
    signal = Signal("OI_ANOMALY", 80, "HIGH", 0.9, {})
    decision = await AlertPolicy(30).decide(FakeRepo(True), "LABUSDT:OI_ANOMALY", signal)
    assert decision.action == "suppress"
    assert decision.reason == "cooldown"


async def test_alert_policy_suppresses_low_confidence() -> None:
    signal = Signal("OI_ANOMALY", 80, "HIGH", 0.5, {})
    decision = await AlertPolicy(30).decide(FakeRepo(False), "LABUSDT:OI_ANOMALY", signal)
    assert decision.action == "suppress"
    assert decision.reason == "low_confidence"

