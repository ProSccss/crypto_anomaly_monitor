# ARCHITECTURE_PRINCIPLES

## P-001
Data Consistency Principle

Each symbol must use a single primary exchange.

All features used for outcome evaluation
(price, volume, funding, OI, basis, candles)
should originate from the same exchange.

Rationale:

Mixing exchanges may create artificial correlations
between unrelated market structures and reduce
the statistical validity of outcome research.

Exception:

Secondary exchanges may be used only as
temporary fallback sources when the primary
exchange is unavailable.

---

## P-002

Previously rejected ideas must not be reintroduced without new evidence.

Evidence means:

* new outcome statistics;
* new research results;
* new exchange limitations;
* new business requirements.

Absence of evidence is not sufficient reason to revisit a rejected decision.
