# MODEL_FREEZE_V27.md

# MODEL FREEZE V2.7

Дата фиксации:
Июнь 2026

Статус:
ACTIVE

---

## Что запрещено менять

До накопления статистически значимого количества outcome:

* Gate A thresholds
* Gate B thresholds
* breakout_probability formula
* squeeze_probability formula
* expected_move_score formula
* setup_context logic
* outcome evaluation logic

---

## Зафиксированные решения

### Решение №1

Удалён volume_percentile из Gate A.

Причина:

Volume-фильтр блокировал PRE_BREAKOUT.

---

### Решение №2

Удалён EMS-фильтр из PRE_BREAKOUT.

Причина:

PRE_BREAKOUT и EMS описывают разные рыночные состояния.

---

### Решение №3

Добавлен setup_context.

Причина:

Необходимо разделять статистику RANGE_COMPRESSION и TREND_COMPRESSION.

---

### Решение №4

Исправлен cooldown bug.

Причина:

Cooldown ранее влиял только на Telegram, но не на сохранение setup.

Исправление:

Cooldown выполняется до создания predictive_setup.

---
## Current Requirements

Current freeze requirements are maintained in PROJECT_STATUS.md.

PROJECT_STATUS.md is the source of truth for active research thresholds and unfreeze conditions.

MODEL_FREEZE_V27 documents the original freeze decision and rationale only.