# Backend API Endpoints

Backend URL: `http://127.0.0.1:8000`

Swagger UI: `http://127.0.0.1:8000/docs`

Авторизация в текущей версии отсутствует. Все расчёты общие. Даты
передаются как `YYYY-MM-DD`, время — в ISO 8601. Границы `date_from` и
`date_to` включаются в выбранный период.

## Frontend flow

1. При открытии dashboard вызвать
   `GET /api/planning-runs?limit=1&offset=0`.
2. Если `items` пустой — показать загрузку Excel.
3. Если расчёт есть — взять `planning_run_id` и вызвать
   `GET /api/planning-runs/{planning_run_id}`.
4. Для dropdown магазина вызвать
   `GET /api/planning-runs/{planning_run_id}/stores`.
5. Перед расчётом можно проверить Excel через
   `POST /api/datasets/preview`.
6. Для расчёта и сохранения вызвать `POST /api/planning/calculate`.
7. KPI, decision plan, календарь, рекомендации и уведомления запрашивать
   отдельными endpoints для выбранного Planning Run.
8. По кнопке AI Explain вызвать `POST /api/assistant/explain`.

## Endpoints

| Method | Endpoint | Параметры | Что делает |
|---|---|---|---|
| `POST` | `/api/datasets/preview` | Multipart: `file` (`.xlsx`) | Распознаёт legacy или официальный multi-sheet Excel, валидирует его и возвращает mapping, количество строк и preview. Файл не сохраняется. |
| `POST` | `/api/planning/calculate` | Multipart: `file`; Query: `target_utilization` для legacy Excel, default `0.85`; `planning_date` optional | Валидирует Excel. Для официального файла возвращает historical calculation либо 90-дневный future forecast, рассчитывает workforce plan и сохраняет Planning Run. |
| `GET` | `/api/planning-runs` | Query: `limit` от `1` до `100`, default `20`; `offset` от `0` | Возвращает `total` и Planning Runs от нового к старому. |
| `GET` | `/api/planning-runs/{planning_run_id}` | Path: `planning_run_id` | Возвращает полный plan, calendar, metadata и IDs без повторной загрузки Excel. |
| `GET` | `/api/planning-runs/{planning_run_id}/stores` | Path: `planning_run_id` | Возвращает отсортированные уникальные `store_id` и `store_count` для frontend dropdown. |
| `GET` | `/api/planning-runs/{planning_run_id}/kpis` | Optional Query: `date_from`, `date_to`, `store_id` | Возвращает операционные KPI для dashboard: coverage, capacity totals, staffing buckets, critical days и emergency hiring actions. |
| `GET` | `/api/planning-runs/{planning_run_id}/decision-plan` | Path: `planning_run_id`; optional Query: `store_id` | Строит rolling workforce plan на 90 дней. С `store_id` возвращает AI Suggestions только выбранного склада. |
| `GET` | `/api/planning-runs/{planning_run_id}/calendar` | Optional Query: `date_from`, `date_to`, `store_id` | Возвращает дни с UAE calendar metadata, severity, coverage, required/available, shortage/surplus и recommendations count. |
| `GET` | `/api/planning-runs/{planning_run_id}/recommendations` | Optional Query: `date_from`, `date_to`, `store_id` | Возвращает capacity context, permanent/outsourced counts, deadlines, priority и reason. |
| `GET` | `/api/planning-runs/{planning_run_id}/notifications` | Optional Query: `date_from`, `date_to`, `store_id` | Возвращает urgent shortage, upcoming shortage, hiring start required и staff surplus alerts. |
| `GET` | `/api/planning-runs/{planning_run_id}/compare` | Path: `planning_run_id`; Query: `baseline_id` от `1` | Сравнивает current Planning Run с baseline и возвращает `delta = current - baseline`. |
| `POST` | `/api/assistant/explain` | JSON: `planning_run_id`; optional `decision_action_id` либо `date_from`, `date_to`, `store_id`; `language` | Объясняет весь scope или одну выбранную AI Suggestion через Ollama; при ошибке LLM возвращает structured fallback. |
| `GET` | `/health` | Нет | Проверяет, что FastAPI отвечает. |
| `GET` | `/health/database` | Нет | Проверяет доступность PostgreSQL. |
| `GET` | `/health/ollama` | Нет | Проверяет, включена ли Ollama, доступна ли она и загружена ли настроенная модель. Fallback backend остаётся доступен независимо от результата. |

## Dataset preview

Для старого плоского Excel endpoint сохраняет прежний response с
`selected_sheet`, `column_mapping`, `validation` и общим `preview`.

Официальный Dataset определяется по рабочим листам `Store_Metadata`,
`Demand_Forecast` и `Courier_Roster`. Для него response содержит:

- `dataset_type: workforce_multi_sheet`;
- `sheets` — все исходные листы, включая информационный `README`;
- `sheet_previews` — отдельный результат каждого из трёх рабочих листов;
- `validation.errors` — блокирующие проблемы;
- `validation.warnings` — неблокирующие проблемы и assumptions.

Каждый элемент `sheet_previews` возвращает `source_sheet`, `canonical_sheet`,
`original_columns`, `column_mapping`, canonical `columns`, полный `row_count` и
не более пяти строк в `preview`. Проверяется весь workbook, но capacity здесь не
рассчитывается и данные в PostgreSQL не сохраняются.

## Planning calculate

Для официального workbook endpoint выполняет loader, validation, суточную
агрегацию и Capacity Engine. Одна строка `plan` соответствует одному магазину
за один день. Исходные 30-минутные строки суммируются, но сам Excel не
изменяется. Query-параметр `target_utilization` применяется только к legacy
Excel.

Official response дополнительно содержит:

- `dataset_type: workforce_multi_sheet`;
- `forecast_mode`: `historical_workbook` или `future_90_days`;
- `model_version`: `catboost-daily-residual-v1` для исторических дат либо
  `catboost-daily-future-v1` для будущих;
- `planning_grain: store_day`;
- `prediction_source`: `catboost`, `catboost_future` или соответствующий
  baseline fallback;
- `prediction_fallback_reason` — `null` on successful CatBoost inference;
- `historical_date_to` — последняя дата исходной истории;
- `horizon_start` и `horizon_end` для future mode;
- normalization `assumptions` и `validation_warnings`;
- `store_name`, `emirate` и `zone` в каждой plan row;
- дневные `required_courier_hours`, `available_courier_hours` и
  `available_delivery_capacity`;
- `baseline_forecast_shipments`, `predicted_shipments` и
  `planning_demand_shipments` в каждой plan row;
- Friday/Saturday weekend metadata из Dataset.

Если `planning_date` позже последней даты истории, endpoint создаёт по 90 новых
дней для каждого магазина. Недельное продолжение Excel forecast служит
baseline, а отдельная CatBoost-модель корректирует его по store, calendar и
прошлым значениям demand. Для исходных 10 магазинов response содержит 900
`plan` rows. Будущие строки не содержат `actual_shipments`.

Если `planning_date` не передан, используется текущая дата сервера. Если она
находится внутри периода Excel, сохраняется прежний historical flow. Если
future CatBoost недоступна, используется `seasonal_naive` без остановки API.

Блокирующая проблема одного из трёх листов возвращает `422`. Warnings не
останавливают расчёт. Нормализованные данные сохраняются в `Dataset`, а полный
результат — в новом `PlanningRun`. Legacy response и расчёты сохранены без
изменения.

## Важное поведение

- Повторная загрузка одинакового Excel использует существующий Dataset, но создаёт
  новый Planning Run.
- Backend возвращает смысловой `severity`. Цвет для него выбирает frontend.
- В compare отрицательный `shortage_courier_slots` в `delta` означает, что дефицит
  уменьшился.

## Фильтры

Endpoints `kpis`, `calendar`, `recommendations` и `notifications` поддерживают
одинаковые фильтры:

| Параметр | Описание |
|---|---|
| `date_from` | Начало периода в формате `YYYY-MM-DD`, включительно |
| `date_to` | Конец периода в формате `YYYY-MM-DD`, включительно |
| `store_id` | Фильтр по конкретному магазину |

Если `date_from` позже `date_to`, backend возвращает `422`.

## UAE calendar metadata

Каждый элемент `calendar` содержит:

```json
{
  "date": "2026-08-01",
  "is_weekend": true,
  "is_public_holiday": false,
  "holiday_name": null
}
```

Legacy flow использует Saturday/Sunday как календарный UAE weekend по
умолчанию. Official flow использует подтверждённые Friday/Saturday значения из
Dataset. Эти поля являются информационными и сами не изменяют forecast,
capacity или availability. Справочник public holidays пока пуст.

## KPI

`GET /api/planning-runs/{planning_run_id}/kpis` считает показатели только по
строкам, попавшим в выбранные фильтры. Для official flow строки имеют grain
`store_day`, а coverage считается по требуемым и доступным courier-hours.
Legacy flow продолжает использовать прежние временные интервалы.

- `coverage_percent` — доля покрытого спроса, максимум 100%;
- `understaffed_buckets` — интервалы с дефицитом;
- `balanced_buckets` — интервалы без дефицита и избытка;
- `overstaffed_buckets` — интервалы с избытком;
- `critical_days` — дни со статусом `critical`;
- `emergency_hiring_actions` — интервалы с причиной
  `emergency_outsourcing_required`.

Стоимость, экономия и фактический SLA не возвращаются, пока официальный Dataset
не содержит необходимых исходных данных.

## Rolling decision plan

`GET /api/planning-runs/{planning_run_id}/decision-plan` использует сохранённый
`plan` и строит действия на 90 календарных дней, включая `planning_date`.
Planning Run не изменяется, а результат пересчитывается одинаково при каждом
запросе.

Для страницы конкретного склада frontend передаёт optional фильтр:

```text
GET /api/planning-runs/1/decision-plan?store_id=QED_DXB_01
```

Без `store_id` endpoint возвращает actions всех складов. Response всегда
содержит поле `store_id`: выбранное значение или `null`.

Горизонты:

- сегодня — `emergency_outsourcing`; внутридневные reallocation и overtime
  остаются недоступны при daily grain;
- `1–3` дня — `store_transfer` из подтверждённого surplus другого store на ту
  же дату; непокрытый остаток становится `emergency_outsourcing`;
- `4–29` дней (`one_week_to_one_month`) — `planned_outsourcing` через FTC;
- `30–90` дней — `planned_outsourcing` для temporary shortage и
  `permanent_hiring` для persistent shortage с outsourcing bridge до окончания
  60-дневного lead time.

Shortage считается `persistent`, если присутствует минимум в 5 разных днях или
в 3 разных ISO-неделях внутри соответствующего горизонта. Одно действие
агрегирует несколько time buckets. Поле `couriers` содержит максимальный
одновременный shortage среди покрываемых buckets, а не их сумму.

Каждое действие содержит:

```json
{
  "action_id": "DXB-001:one_to_three_months:permanent_hiring:2026-10-05:2026-10-09",
  "store_id": "DXB-001",
  "shortage_period": {
    "date_from": "2026-10-05",
    "date_to": "2026-10-09"
  },
  "shortage_type": "persistent",
  "action_type": "permanent_hiring",
  "couriers": 6,
  "deadline": "2026-08-06",
  "priority": "medium",
  "reason": "persistent_shortage_requires_permanent_hiring",
  "decision_basis": {
    "covered_shortage_days": 5,
    "covered_shortage_weeks": 2,
    "persistent_shortage_days_total": 5,
    "persistent_shortage_weeks_total": 2
  },
  "evidence": {
    "prediction_source": "catboost",
    "model_version": "catboost-daily-residual-v1",
    "baseline_orders_total": 1250.0,
    "predicted_orders_total": 1284.5,
    "prediction_correction_total": 34.5,
    "peak_gap": {
      "date": "2026-10-07",
      "required_couriers": 18,
      "available_couriers": 12,
      "shortage_before_action": 6,
      "action_gap_couriers": 6
    }
  },
  "covered_time_buckets": [
    "2026-10-05T09:00:00"
  ]
}
```

`covered_shortage_*` описывает только период конкретного action.
`persistent_shortage_*_total` описывает полный устойчивый дефицит, на основании
которого Decision Engine выбрал persistent strategy. Для outsourcing bridge эти
значения могут различаться.

`store_transfer` имеет `status: active_rule_based`, использует только свободный
surplus и требует подтверждения менеджера. Store того же emirate получает
приоритет. `schedule_reallocation` и `overtime` остаются
`pending_input_data`, поскольку daily plan не содержит внутридневной сменной
ёмкости и допустимого overtime. `limitations` явно описывает эти границы.

## AI Explain

`POST /api/assistant/explain` принимает `planning_run_id`, опциональные
`date_from`, `date_to`, `store_id`, `decision_action_id` и `language` (`en` или
`ru`). `decision_action_id` нельзя объединять с store/date filters.
Неиспользуемые поля нужно удалять из JSON или передавать как `null`.
Swagger placeholder `"string"` нельзя отправлять как `store_id`.

Весь Planning Run:

```json
{
  "planning_run_id": 1,
  "language": "en"
}
```

Один магазин:

```json
{
  "planning_run_id": 1,
  "store_id": "DXB-001",
  "language": "en"
}
```

Одна AI Suggestion после клика по карточке:

```json
{
  "planning_run_id": 2,
  "decision_action_id": "QED_AUH_01:today:emergency_outsourcing:2026-04-28:2026-04-28",
  "language": "en"
}
```

Frontend получает `action_id` из
`GET /api/planning-runs/{planning_run_id}/decision-plan`, передаёт его в
`/api/assistant/explain` и показывает `message` в открытой карточке. Backend
автоматически ограничивает context магазином и периодом выбранного action.
Для выбранной карточки Ollama объясняет только это действие в 4 коротких
пунктах и не перечисляет пустые горизонты. В LLM отправляется только
`selected_action` с его backend evidence; полный context остаётся в HTTP
response для frontend, но не используется моделью при объяснении карточки.
`predicted_orders_total` объясняется как сумма за покрываемый период, а
required/available/shortage — как значения дня `peak_gap`.

Магазин за период:

```json
{
  "planning_run_id": 1,
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "store_id": "DXB-001",
  "language": "en"
}
```

При успешном ответе Ollama backend возвращает `source: ollama` и текст в
`message`. Если LLM выключена, недоступна или не успела ответить, backend вернёт
`source: structured_fallback`, `message: null` и тот же `context`.

`context.decision_plan` содержит отфильтрованные rolling actions: transfer,
FTC outsourcing, emergency outsourcing или FTE hiring. Ollama только объясняет
эти действия и не меняет их числа, сроки или тип.

`context.decision_plan.summary` покрывает все действия, а `items` содержит
сбалансированные примеры каждого горизонта и action type. В каждом action блок
`evidence` показывает цепочку Excel baseline → CatBoost demand → required и
available couriers → shortage.

Числа и кадровые решения формирует backend, а не LLM. Если фильтры не нашли
строк, `context.scope.plan_rows` будет равен `0`.

## Основные ошибки

| Status | Значение |
|---|---|
| `400` | Неверный формат файла или Excel невозможно прочитать |
| `404` | Planning Run не найден |
| `404` | Переданный `decision_action_id` не существует в Planning Run |
| `422` | Ошибка валидации или неправильный диапазон дат |
| `503` | PostgreSQL недоступен либо Ollama/настроенная модель недоступна при health-check |
