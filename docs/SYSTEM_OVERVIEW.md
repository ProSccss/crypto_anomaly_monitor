                    ┌──────────────────┐
                    │    Bybit API     │
                    └────────┬─────────┘
                             │
                             ▼
                     Scanner Pipeline
                             │
                  Feature Extraction
                             │
                             ▼
                     FeatureSnapshot
                             │
                             ▼
                    Predictive Engine
                             │
                             ▼
                     ResearchService
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       Telegram Console   Daily Reports   Future REST API
              │
              ▼
          Researcher

Scanner — собирает данные.
Feature Engine — рассчитывает признаки.
Predictive Engine — строит гипотезы.
ResearchService — единая точка анализа.
Telegram Console — интерфейс исследователя.