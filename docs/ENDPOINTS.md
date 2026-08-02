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
7. Календарь, рекомендации и уведомления запрашивать отдельными
   endpoints с текущими фильтрами dashboard.
8. По кнопке AI Explain вызвать `POST /api/assistant/explain`.

## Endpoints

| Method | Endpoint | Параметры | Что делает |
|---|---|---|---|
| `POST` | `/api/datasets/preview` | Multipart: `file` (`.xlsx`) | Валидирует Excel, возвращает листы, column mapping, issues и первые 5 строк. Файл не сохраняется. |
| `POST` | `/api/planning/calculate` | Multipart: `file`; Query: `target_utilization` в диапазоне `(0, 1]`, default `0.85`; `planning_date` optional, default — текущая дата backend | Валидирует Excel, рассчитывает plan и calendar, сохраняет Dataset и Planning Run. Возвращает результат, `dataset_id` и `planning_run_id`. |
| `GET` | `/api/planning-runs` | Query: `limit` от `1` до `100`, default `20`; `offset` от `0` | Возвращает `total` и Planning Runs от нового к старому. |
| `GET` | `/api/planning-runs/{planning_run_id}` | Path: `planning_run_id` | Возвращает полный plan, calendar, metadata и IDs без повторной загрузки Excel. |
| `GET` | `/api/planning-runs/{planning_run_id}/stores` | Path: `planning_run_id` | Возвращает отсортированные уникальные `store_id` и `store_count` для frontend dropdown. |
| `GET` | `/api/planning-runs/{planning_run_id}/calendar` | Optional Query: `date_from`, `date_to`, `store_id` | Возвращает дни с severity, coverage, required/available, shortage/surplus и recommendations count. |
| `GET` | `/api/planning-runs/{planning_run_id}/recommendations` | Optional Query: `date_from`, `date_to`, `store_id` | Возвращает capacity context, permanent/outsourced counts, deadlines, priority и reason. |
| `GET` | `/api/planning-runs/{planning_run_id}/notifications` | Optional Query: `date_from`, `date_to`, `store_id` | Возвращает urgent shortage, upcoming shortage, hiring start required и staff surplus alerts. |
| `GET` | `/api/planning-runs/{planning_run_id}/compare` | Path: `planning_run_id`; Query: `baseline_id` от `1` | Сравнивает current Planning Run с baseline и возвращает `delta = current - baseline`. |
| `POST` | `/api/assistant/explain` | JSON: `planning_run_id`; optional `date_from`, `date_to`, `store_id`, `language` | Возвращает human-friendly Ollama explanation или structured fallback вместе с готовым backend context. |
| `GET` | `/health` | Нет | Проверяет, что FastAPI отвечает. |
| `GET` | `/health/database` | Нет | Проверяет доступность PostgreSQL. |

## Важное поведение

- Повторная загрузка одинакового Excel использует существующий Dataset, но создаёт
  новый Planning Run.
- Backend возвращает смысловой `severity`. Цвет для него выбирает frontend.
- В compare отрицательный `shortage_courier_slots` в `delta` означает, что дефицит
  уменьшился.

## Фильтры

Endpoints `calendar`, `recommendations` и `notifications` поддерживают одинаковые
фильтры:

| Параметр | Описание |
|---|---|
| `date_from` | Начало периода в формате `YYYY-MM-DD`, включительно |
| `date_to` | Конец периода в формате `YYYY-MM-DD`, включительно |
| `store_id` | Фильтр по конкретному магазину |

Если `date_from` позже `date_to`, backend возвращает `422`.

## AI Explain

`POST /api/assistant/explain` принимает `planning_run_id`, опциональные
`date_from`, `date_to`, `store_id` и `language` (`en` или `ru`).
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

Числа и кадровые решения формирует backend, а не LLM. Если фильтры не нашли
строк, `context.scope.plan_rows` будет равен `0`.

## Основные ошибки

| Status | Значение |
|---|---|
| `400` | Неверный формат файла или Excel невозможно прочитать |
| `404` | Planning Run не найден |
| `422` | Ошибка валидации или неправильный диапазон дат |
| `503` | PostgreSQL недоступен при проверке базы |
