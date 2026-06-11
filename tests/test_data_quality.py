from tests.test_scoring import snapshot
from app.services.data_quality import DataQualityService


def test_data_quality_is_good_for_complete_snapshot() -> None:
    item = snapshot(0, basis="10")
    item = item.__class__(**{**item.__dict__, "raw_payload": {"spot_source": "bybit_spot_ticker", "ratio": {"buyRatio": "0.5"}}})
    report = DataQualityService().assess_snapshot(item)
    assert report.status == "GOOD"
    assert report.score == 100


def test_data_quality_degrades_but_survives_missing_optional_ratio() -> None:
    item = snapshot(0, basis="10")
    item = item.__class__(
        **{
            **item.__dict__,
            "long_ratio": None,
            "short_ratio": None,
            "raw_payload": {"spot_source": "binance_spot_ticker", "ratio": {}},
        }
    )
    report = DataQualityService().assess_snapshot(item)
    assert report.status == "DEGRADED"
    assert report.score == 85
    assert "long_ratio" in report.missing_fields


def test_data_quality_marks_unavailable_spot_as_bad() -> None:
    item = snapshot(0, basis="0")
    item = item.__class__(
        **{
            **item.__dict__,
            "spot_price": None,
            "basis_bps": None,
            "raw_payload": {"spot_source": "unavailable", "ratio": {"buyRatio": "0.5"}},
        }
    )
    report = DataQualityService().assess_snapshot(item)
    assert report.status == "BAD"
    assert report.score == 55
