# Docker Run (Backend + Frontend)

## Запуск

Из корня repository, где расположен `compose.yaml`:

```bash
docker compose up --build -d
```

Команда собирает FastAPI image, запускает PostgreSQL, ждёт готовности базы,
применяет `alembic upgrade head` и запускает Uvicorn, а также собирает
frontend (Vite build) и раздаёт его статику через Nginx.

Compose собирает backend с build context `./backend`, frontend — с build
context `./frontend` (multi-stage: `node` для сборки, `nginx:alpine` для
раздачи `dist`).

После запуска:

- Frontend: `http://127.0.0.1:3000`;
- API: `http://127.0.0.1:8000`;
- Swagger UI: `http://127.0.0.1:8000/docs`;
- ReDoc: `http://127.0.0.1:8000/redoc`;
- raw OpenAPI schema: `http://127.0.0.1:8000/openapi.json`;
- PostgreSQL с хоста: `localhost:5433`.

`.env` опционален: Compose имеет безопасные development defaults. Для изменения
портов, CORS или Ollama нужно скопировать `.env.example` в `.env` и изменить
значения локально. Реальный `.env` не добавляется в Git.

Frontend сейчас работает на статических mock-данных и не обращается к API —
`FRONTEND_ORIGINS` уже включает его origin (`http://localhost:3000`) на будущее,
когда экраны подключат к реальным endpoints.

## Проверка

```bash
docker compose ps
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/database
curl -I http://127.0.0.1:3000
```

Backend и postgres должны иметь статус `healthy`, health endpoints — вернуть
HTTP `200`, а `http://127.0.0.1:3000` — отдать `200` с HTML дашборда.

## Логи и остановка

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose stop
```

`docker compose stop` не удаляет PostgreSQL volume и сохранённые Planning Runs.

## Ollama

Ollama не входит в Compose и остаётся внешним опциональным сервисом. Если она
выключена или недоступна из backend-контейнера, `/api/assistant/explain`
возвращает `structured_fallback`; остальные endpoints продолжают работать.
