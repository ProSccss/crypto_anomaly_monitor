from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain import Liquidation, Snapshot
from app.services.scoring import SignalEngine

NOW = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)


def snapshot(
    minutes_ago: int,
    *,
    price: str = "1",
    oi: str = "1000000",
    funding: str = "0",
    basis: str = "0",
) -> Snapshot:
    value = Decimal(price)
    return Snapshot(
        ts=NOW - timedelta(minutes=minutes_ago),
        symbol="LABUSDT",
        last_price=value,
        mark_price=value,
        index_price=value,
        spot_price=value,
        open_interest_usd=Decimal(oi),
        volume_24h_usd=Decimal("10000000"),
        funding_rate=Decimal(funding),
        funding_8h_equivalent=Decimal(funding),
        long_ratio=Decimal(".5"),
        short_ratio=Decimal(".5"),
        basis_bps=Decimal(basis),
    )


def history(current: Snapshot, *, p15=None, p1h=None, p4h=None) -> list[Snapshot]:
    return [
        p4h or snapshot(240),
        p1h or snapshot(60),
        p15 or snapshot(15),
        current,
    ]


def liquidation(side: str, notional: str) -> Liquidation:
    return Liquidation(
        ts=NOW - timedelta(minutes=1),
        symbol="LABUSDT",
        liquidated_side=side,
        quantity=Decimal(notional),
        price=Decimal("1"),
        notional_usd=Decimal(notional),
        source_event_id=f"{side}-{notional}",
    )


def types(items) -> set[str]:
    return {item.signal_type for item in items}


def test_short_squeeze() -> None:
    current = snapshot(0, price="1.12", oi="780000", funding="-0.01")
    result = SignalEngine().calculate(history(current), [liquidation("short", "600000")])
    assert "SHORT_SQUEEZE" in types(result)


def test_long_squeeze() -> None:
    current = snapshot(0, price=".88", oi="780000", funding="0.01")
    result = SignalEngine().calculate(history(current), [liquidation("long", "600000")])
    assert "LONG_SQUEEZE" in types(result)


def test_distribution_after_rise() -> None:
    current = snapshot(0, price="1.19", oi="750000")
    result = SignalEngine().calculate(
        history(current, p15=snapshot(15, price="1.18", oi="800000"), p1h=snapshot(60, price="1.18"), p4h=snapshot(240, price="1")),
        [],
    )
    assert "DISTRIBUTION_AFTER_RISE" in types(result)


def test_accumulation_long_biased() -> None:
    current = snapshot(0, price="1.01", oi="1500000", funding=".002")
    result = SignalEngine().calculate(history(current, p1h=snapshot(60, oi="1000000"), p4h=snapshot(240, oi="900000")), [])
    assert "ACCUMULATION_LONG_BIASED" in types(result)


def test_oi_anomaly() -> None:
    current = snapshot(0, oi="1400000")
    result = SignalEngine().calculate(history(current), [])
    assert "OI_ANOMALY" in types(result)


def test_funding_anomaly() -> None:
    current = snapshot(0, funding=".01")
    result = SignalEngine().calculate(history(current), [])
    assert "FUNDING_ANOMALY_POSITIVE" in types(result)


def test_basis_anomaly() -> None:
    current = snapshot(0, basis="250")
    result = SignalEngine().calculate(history(current), [])
    assert "BASIS_ANOMALY_PREMIUM" in types(result)


def test_insufficient_history_is_ignored() -> None:
    assert SignalEngine().calculate([snapshot(0)], []) == []

