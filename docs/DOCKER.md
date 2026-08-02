# Backend Docker Run

## Запуск

Из корня backend:

```bash
docker compose up --build -d
```

Команда собирает FastAPI image, запускает PostgreSQL, ждёт готовности базы,
применяет `alembic upgrade head` и запускает Uvicorn.

После запуска:

- API: `http://127.0.0.1:8000`;
- Swagger: `http://127.0.0.1:8000/docs`;
- PostgreSQL с хоста: `localhost:5433`.

`.env` опционален: Compose имеет безопасные development defaults. Для изменения
портов, CORS или Ollama нужно скопировать `.env.example` в `.env` и изменить
значения локально. Реальный `.env` не добавляется в Git.

## Проверка

```bash
docker compose ps
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/database
```

Оба контейнера должны иметь статус `healthy`, а health endpoints — вернуть
HTTP `200`.

## Логи и остановка

```bash
docker compose logs -f backend
docker compose stop
```

`docker compose stop` не удаляет PostgreSQL volume и сохранённые Planning Runs.

## Ollama

Ollama не входит в Compose и остаётся внешним опциональным сервисом. Если она
выключена или недоступна из backend-контейнера, `/api/assistant/explain`
возвращает `structured_fallback`; остальные endpoints продолжают работать.
