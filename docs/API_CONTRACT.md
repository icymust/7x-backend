# Backend API contract for frontend

Base URL для локальной разработки: `http://127.0.0.1:8000`.

Авторизация для hackathon MVP отсутствует. Все Planning Runs общие. Даты и
время передаются в ISO 8601. Границы `date_from` и `date_to` включаются в
результат.

## Рекомендуемый flow frontend

1. При открытии dashboard вызвать
   `GET /api/planning-runs?limit=1&offset=0`.
2. Если `items` пустой, показать форму загрузки Excel.
3. Если есть запись, получить полный результат через
   `GET /api/planning-runs/{planning_run_id}`.
4. После новой загрузки использовать результат
   `POST /api/planning/calculate` без дополнительного GET-запроса.
5. Для календарного экрана использовать отдельные calendar и recommendations
   endpoints с одинаковыми фильтрами периода и магазина.

## POST /api/planning/calculate

Принимает `.xlsx` как `multipart/form-data` в поле `file`.

Query parameters:

- `target_utilization`: число больше `0` и не больше `1`, default `0.85`;
- `planning_date`: опциональная дата `YYYY-MM-DD`.

Успешный ответ содержит:

- `filename`;
- `target_utilization`;
- `planning_date`;
- `row_count`;
- `plan`: подробные capacity rows с `recommendation`;
- `calendar`: агрегированные daily summaries;
- `dataset_id`;
- `planning_run_id`.

Backend сохраняет Dataset и Planning Run до возврата успешного ответа.
Одинаковый файл повторно использует существующий Dataset по SHA-256 checksum,
но каждый расчёт создаёт новый Planning Run.

## GET /api/planning-runs

Возвращает историю расчётов от новых к старым.

Query parameters:

- `limit`: от `1` до `100`, default `20`;
- `offset`: от `0`, default `0`.

Форма ответа:

```json
{
  "total": 35,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "planning_run_id": 35,
      "dataset_id": 8,
      "filename": "capacity_august.xlsx",
      "planning_date": "2026-08-01",
      "created_at": "2026-08-01T20:00:00+00:00",
      "target_utilization": 0.85,
      "model_version": "baseline-v1",
      "row_count": 120
    }
  ]
}
```

`total` — количество всех Planning Runs, а не только элементов текущей
страницы.

## GET /api/planning-runs/{planning_run_id}

Возвращает полный сохранённый результат: `plan`, `calendar`, metadata и IDs.
Используется для восстановления dashboard без повторной загрузки Excel.

Неизвестный ID возвращает `404` с `Planning run not found`.

## GET /api/planning-runs/{planning_run_id}/calendar

Query parameters:

- `date_from`: опциональная дата `YYYY-MM-DD`;
- `date_to`: опциональная дата `YYYY-MM-DD`;
- `store_id`: опциональный ID магазина.

Форма ответа:

```json
{
  "planning_run_id": 5,
  "dataset_id": 1,
  "store_id": "DXB-001",
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "row_count": 2,
  "calendar": []
}
```

Каждый calendar item содержит `date`, `severity`, `coverage_percent`, required,
available, shortage и surplus courier slots, affected stores и recommendations
count. Backend возвращает смысловой `severity`; конкретный цвет выбирает
frontend.

## GET /api/planning-runs/{planning_run_id}/recommendations

Использует те же `date_from`, `date_to` и `store_id`.

Форма ответа:

```json
{
  "planning_run_id": 5,
  "dataset_id": 1,
  "store_id": "DXB-001",
  "date_from": null,
  "date_to": null,
  "row_count": 2,
  "recommendations": []
}
```

Каждый item содержит магазин, time bucket, required/available couriers,
shortage/surplus и структурированную recommendation: permanent/outsourced
counts, deadlines, priority и reason.

## Ошибки

- `400`: файл не `.xlsx` или Excel невозможно прочитать;
- `404`: Planning Run не найден;
- `422`: validation error или `date_from` позже `date_to`;
- `503`: PostgreSQL недоступен для `/health/database`.

Swagger доступен по `/docs` и используется как интерактивная документация
актуального backend API.
