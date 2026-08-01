# API contract для frontend

Локальный backend: `http://127.0.0.1:8000`

Swagger: `http://127.0.0.1:8000/docs`

Авторизации нет. Все расчёты общие. Даты передаются как `YYYY-MM-DD`, время —
в ISO 8601. `date_from` и `date_to` включаются в выбранный период.

## Основной flow

1. При открытии dashboard вызвать
   `GET /api/planning-runs?limit=1&offset=0`.
2. Если `items` пустой — показать загрузку Excel.
3. Если расчёт есть — взять его `planning_run_id` и вызвать
   `GET /api/planning-runs/{id}`.
4. После загрузки нового Excel вызвать `POST /api/planning/calculate` и сразу
   показать данные из ответа.
5. Для календаря и рекомендаций использовать отдельные endpoints с фильтрами.

## 1. Preview Excel

`POST /api/datasets/preview`

- Request: `.xlsx` в multipart-поле `file`.
- Response: листы, колонки, column mapping, validation issues и первые пять
  строк.
- Файл не сохраняется и расчёт не запускается.

## 2. Рассчитать и сохранить

`POST /api/planning/calculate`

- Request: `.xlsx` в multipart-поле `file`.
- Query: `target_utilization` — default `0.85`.
- Query: `planning_date` — опциональная дата.
- Response: `plan`, `calendar`, `dataset_id`, `planning_run_id`, filename,
  planning date и row count.

Backend сначала валидирует Excel, рассчитывает capacity и recommendations,
сохраняет результат в PostgreSQL и только после этого отвечает frontend.

Повторная загрузка одинакового файла использует существующий Dataset, но
создаёт новый Planning Run.

## 3. Список расчётов

`GET /api/planning-runs?limit=20&offset=0`

- `limit`: от `1` до `100`.
- `offset`: от `0`.
- Response: `total`, `limit`, `offset`, `items`.
- `items` отсортированы от нового расчёта к старому.

Каждый item содержит IDs, filename, planning date, created time, utilization,
model version и row count. `total` — количество всех сохранённых расчётов.

## 4. Полный сохранённый расчёт

`GET /api/planning-runs/{planning_run_id}`

Возвращает полный `plan`, `calendar`, metadata и IDs. Используется для
восстановления dashboard без повторной загрузки Excel.

## 5. Календарь

`GET /api/planning-runs/{planning_run_id}/calendar`

Опциональные query parameters:

- `date_from`;
- `date_to`;
- `store_id`.

Response содержит `calendar`, `row_count`, выбранные фильтры и IDs. Каждый день
содержит severity, coverage, required/available, shortage/surplus, affected
stores и recommendations count.

Backend возвращает смысловой severity. Цвет для него выбирает frontend.

## 6. Рекомендации

`GET /api/planning-runs/{planning_run_id}/recommendations`

Использует те же `date_from`, `date_to` и `store_id`.

Response содержит capacity context и recommendation для каждой подходящей
строки: permanent/outsourced counts, deadlines, priority и reason.

## 7. Уведомления

`GET /api/planning-runs/{planning_run_id}/notifications`

Использует те же `date_from`, `date_to` и `store_id`.

Response содержит dashboard alerts: urgent staff shortage, upcoming shortage,
hiring start required и staff surplus. Каждый alert содержит severity, магазин,
дату, shortage/surplus, hiring counts, reason и action deadline.

## 8. Сравнение расчётов

`GET /api/planning-runs/{current_id}/compare?baseline_id={old_id}`

- `baseline_id` — старый расчёт.
- `current_id` — новый расчёт.
- Response: `baseline`, `current`, `delta`.
- Формула: `delta = current - baseline`.

Отрицательная `shortage_courier_slots` в delta означает, что дефицит уменьшился.

## 9. AI-объяснение

`POST /api/assistant/explain`

Request JSON: `planning_run_id`, опциональные `date_from`, `date_to`,
`store_id` и `language` (`en` или `ru`).

Response содержит `source`, `message` и компактный `context` с capacity,
daily summary, recommendations и notifications. Пока Ollama не подключена,
backend возвращает `source: structured_fallback` и `message: null`.
Числа и кадровые решения формирует backend, а не LLM.

## Служебные endpoints

- `GET /health` — FastAPI работает.
- `GET /health/database` — PostgreSQL доступен.

## Ошибки

- `400` — неверный формат или Excel невозможно прочитать.
- `404` — Planning Run не найден.
- `422` — validation error или неправильный диапазон дат.
- `503` — PostgreSQL недоступен в database health check.
