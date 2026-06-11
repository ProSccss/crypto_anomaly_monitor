from dataclasses import dataclass
from typing import Protocol

from app.domain import Signal


class CooldownRepository(Protocol):
    async def is_in_cooldown(self, fingerprint: str, minutes: int) -> bool:
        ...


@dataclass(frozen=True)
class AlertDecision:
    action: str
    reason: str


class AlertPolicy:
    def __init__(self, cooldown_minutes: int) -> None:
        self.cooldown_minutes = cooldown_minutes

    async def decide(self, repo: CooldownRepository, fingerprint: str, signal: Signal) -> AlertDecision:
        if signal.confidence < 0.60:
            return AlertDecision("suppress", "low_confidence")
        if await repo.is_in_cooldown(fingerprint, self.cooldown_minutes):
            return AlertDecision("suppress", "cooldown")
        return AlertDecision("send", "eligible")
