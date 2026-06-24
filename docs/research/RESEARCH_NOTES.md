# Research Notes

## 2026-06-24

Dataset:

99 complete outcomes

---

### Finding #1

CONTINUATION significantly outperforms PRE_BREAKOUT.

Metrics:

- CONTINUATION Hit5 = 87.5%
- PRE_BREAKOUT Hit5 = 34.7%

CONTINUATION currently shows the strongest statistical edge.

---

### Finding #2

TREND_COMPRESSION appears significantly stronger than RANGE_COMPRESSION.

Metrics:

- TREND_COMPRESSION AvgMFE4h = 17.3%
- RANGE_COMPRESSION AvgMFE4h = 2.0%

TREND_COMPRESSION currently provides the highest-quality setups.

---

### Finding #3

PRE_BREAKOUT + RANGE_COMPRESSION appears statistically weak.

Metrics:

- Count = 31
- Hit5 = 8%
- AvgMFE4h = 2.0%

This is currently the weakest statistically meaningful population.

Candidate for future filtering in V2.8.

No model changes yet.

---

### Finding #4

LONG setups outperform SHORT setups.

Metrics:

- LONG Hit5 = 75%
- SHORT Hit5 = 40%

Need larger sample size before drawing final conclusions.

---

### Finding #5

HUSDT is currently the strongest tracked symbol.

Metrics:

- Count = 55
- Hit5 = 79.4%
- AvgMFE4h = 16.8%

Need additional symbols and larger datasets before symbol-specific conclusions.

---

Current Conclusion

The model already shows statistically meaningful separation between strong and weak setup populations.

Most important observation:

PRE_BREAKOUT + RANGE_COMPRESSION consistently underperforms.

Priority:

Continue outcome collection until 150–200 complete outcomes before considering model modifications.