from dataclasses import dataclass

from app.domain import Snapshot


REQUIRED_NUMERIC_FIELDS = (
    "last_price",
    "mark_price",
    "index_price",
    "open_interest_usd",
    "volume_24h_usd",
    "funding_rate",
    "funding_8h_equivalent",
)
OPTIONAL_FIELDS = ("long_ratio", "short_ratio")


@dataclass(frozen=True)
class DataQualityReport:
    score: float
    status: str
    missing_fields: list[str]
    source_errors: list[str]
    is_complete: bool


class DataQualityService:
    def assess_snapshot(self, snapshot: Snapshot) -> DataQualityReport:
        missing = self._missing_fields(snapshot)
        errors = self._source_errors(snapshot)
        score = 100.0
        for field in missing:
            score -= 5.0 if field in OPTIONAL_FIELDS else 15.0
        for error in errors:
            score -= 5.0 if error in {"long_short_ratio_unavailable", "spot_reference_fallback_to_index"} else 15.0
        score = max(0.0, min(100.0, score))
        status = "GOOD" if score >= 90 else "DEGRADED" if score >= 60 else "BAD"
        return DataQualityReport(
            score=score,
            status=status,
            missing_fields=missing,
            source_errors=errors,
            is_complete=not missing and status == "GOOD",
        )

    @staticmethod
    def _missing_fields(snapshot: Snapshot) -> list[str]:
        missing: list[str] = []
        for field in REQUIRED_NUMERIC_FIELDS:
            value = getattr(snapshot, field)
            if value is None or value <= 0 and field not in {"funding_rate", "funding_8h_equivalent"}:
                missing.append(field)
        if snapshot.spot_price is None:
            missing.append("spot_price")
        if snapshot.basis_bps is None:
            missing.append("basis_bps")
        if snapshot.long_ratio is None:
            missing.append("long_ratio")
        if snapshot.short_ratio is None:
            missing.append("short_ratio")
        return missing

    @staticmethod
    def _source_errors(snapshot: Snapshot) -> list[str]:
        errors: list[str] = []
        spot_source = snapshot.spot_source or snapshot.raw_payload.get("spot_source")
        if spot_source in {None, "unavailable"}:
            errors.append("spot_reference_unavailable")
        elif spot_source == "bybit_derivatives_index_price":
            errors.append("spot_reference_fallback_to_index")
        if not snapshot.raw_payload.get("ratio"):
            errors.append("long_short_ratio_unavailable")
        return errors
