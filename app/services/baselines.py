from statistics import median


def clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, value))


def scale(value: float, soft: float, hard: float) -> float:
    if hard <= soft:
        return 0.0
    return clip(100.0 * (value - soft) / (hard - soft))


def pct_change(current: float, previous: float) -> float:
    return 100.0 * (current - previous) / previous if previous else 0.0


class BaselineService:
    @staticmethod
    def robust_zscore(value: float, sample: list[float]) -> float:
        clean = [item for item in sample if item is not None]
        if len(clean) < 5:
            return 0.0
        med = median(clean)
        deviations = [abs(item - med) for item in clean]
        mad = median(deviations)
        if mad == 0:
            return 0.0
        return 0.6745 * (value - med) / mad

    @staticmethod
    def percentile_rank(value: float, sample: list[float]) -> float:
        clean = sorted(item for item in sample if item is not None)
        if not clean:
            return 50.0
        below_or_equal = sum(1 for item in clean if item <= value)
        return 100.0 * below_or_equal / len(clean)

    @staticmethod
    def median_or(value: float, sample: list[float]) -> float:
        clean = [item for item in sample if item is not None]
        return median(clean) if clean else value

