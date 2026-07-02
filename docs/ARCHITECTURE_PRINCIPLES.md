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

---
## P-003

The purpose of research is to improve trading decisions.

Research itself is not a project goal.

Every research result should eventually answer one of three questions:

• Should we enter?
• Should we avoid?
• Should we manage the position differently?