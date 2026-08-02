# Заметки по backend 7X

## Полезные команды

```bash
# Активировать виртуальное окружение Python
source .venv/bin/activate

# Запустить backend в режиме разработки
uvicorn app.main:app --reload

# Запустить все тесты
pytest

# Запустить Docker на macOS
colima start

# Запустить PostgreSQL проекта
docker compose up -d

# Проверить состояние контейнера
docker compose ps

# Посмотреть логи PostgreSQL
docker compose logs postgres

# Проверить готовность PostgreSQL
docker compose exec postgres pg_isready -U sevenx -d sevenx

# Открыть консоль PostgreSQL
docker compose exec postgres psql -U sevenx -d sevenx

# Остановить контейнеры проекта без удаления данных
docker compose stop

# Показать текущую версию миграции
alembic current

# Сгенерировать миграцию после изменения models
alembic revision --autogenerate -m "migration description"

# Применить все новые миграции
alembic upgrade head
```

## Архитектура системы

```text
                    Excel от 7X
        demand forecast + workforce + leave
                            |
                            v
              Import → Mapping → Validation
                            |
                            v
               Канонические данные backend
                            |
              ┌─────────────┴─────────────┐
              |                           |
              v                           v
   Исторические actual data       Demand и workforce data
              |                           |
              v                           |
   ML Productivity Estimator              |
   planned; baseline from Excel           |
              |                           |
              └─────────────┬─────────────┘
                            v
                     Capacity Engine
           required / available / shortage / surplus
                            |
                            v
          Workforce Optimization Engine
          planned: Google OR-Tools + cost
          current fallback: rule-based 60/40
                            |
                            v
                Recommendation Engine
          count / deadline / priority / reason
                            |
                            v
              Daily Summary + Calendar
              month / day / date range
                            |
                            v
                    Planning Result
       capacity + optimization + recommendations
              + daily summary + notifications
                            |
              ┌─────────────┴─────────────┐
              |                           |
              v                           v
      Структурированные данные   Explanation Context Builder
                                          |
                                          v
                                 Опциональный Ollama LLM
                                 только объясняет результат
              |                           |
              └─────────────┬─────────────┘
                            v
                       FastAPI API
                            |
                            v
                         Frontend
```

Backend является источником точных значений: количества курьеров, сроков,
приоритетов и кодов причин. Пока ML-модель не подключена, Capacity Engine
использует `productivity_per_courier` из Excel как baseline. После получения
исторических данных ML будет предсказывать это значение. Explanation Context
Builder собирает для выбранного дня или периода capacity, optimization,
recommendations, daily summary и notifications. Опциональный Ollama LLM
может только превратить этот готовый контекст в понятный человеку текст и не
участвует в расчётах.

## Основной flow

1. Пользователь загружает Excel с forecast, workforce и leave.
2. Backend читает файл, сопоставляет колонки и валидирует значения.
3. Productivity берётся из Excel или предсказывается ML-моделью при наличии
   обученной модели и подходящих исторических данных.
4. Capacity Engine рассчитывает required, effective available, shortage и
   surplus по каждому store/time bucket.
5. Сейчас backend использует rule-based permanent/outsourced mix 60/40.
   Workforce Optimization Engine на Google OR-Tools будет добавлен после
   получения полей стоимости и ограничений из официального Dataset.
6. Recommendation Engine формирует количество, deadline, priority и reason.
7. Daily Summary группирует результат по дням для календаря.
8. Explanation Context Builder собирает компактный контекст выбранного дня или
   периода из capacity, optimization, recommendations, daily summary и
   notifications.
9. Ollama опционально превращает этот контекст в понятное HR-объяснение; при
   недоступности LLM возвращается структурированный fallback.
10. FastAPI отдаёт frontend подробный plan, calendar summary и explanations.

## Что уже сделано в backend

- FastAPI-приложение со Swagger и endpoint `/health`.
- Health endpoints для PostgreSQL и опциональной Ollama-модели.
- Загрузка `.xlsx` и preview листов, колонок и первых строк.
- Нормализация названий колонок и mapping aliases во внутренний формат backend.
- Валидация пропусков, дат, чисел, отрицательных значений, productivity,
  дубликатов store/time и количества недоступных курьеров.
- Генератор искусственного Excel для работы до получения официального файла.
- Расчёт capacity для каждого магазина и временного интервала:
  - required couriers;
  - available couriers;
  - shortage и surplus;
  - настраиваемый target utilization;
  - отсутствующие permanent и outsourced из-за отпуска или выходного.
- Endpoint `POST /api/planning/calculate` для расчёта загруженного Excel.
- Rule-based Recommendation Engine:
  - целевое соотношение 60% permanent и 40% outsourced;
  - сколько permanent и outsourced нужно добавить;
  - сроки начала permanent hiring и заказа outsourced;
  - переход на outsourced, если срок permanent hiring уже пропущен;
  - priority и машиночитаемая причина рекомендации.
- Daily Summary Engine для календаря:
  - группировка подробного planning plan по дням;
  - daily coverage, required и available courier slots;
  - daily shortage, surplus и количество затронутых магазинов;
  - количество рекомендаций за день;
  - смысловой статус `normal`, `warning`, `high`, `critical` или `surplus`.
- Поле `calendar` в ответе `POST /api/planning/calculate` для frontend.
- PostgreSQL в Docker Compose с отдельным persistent volume.
- SQLAlchemy engine, sessions и проверка подключения `/health/database`.
- Alembic и две миграции для таблиц `datasets` и `planning_runs`.
- Сохранение нормализованного Dataset с SHA-256 checksum без дубликатов.
- Сохранение каждого нового расчёта как отдельного Planning Run.
- Поля `dataset_id` и `planning_run_id` в ответе
  `POST /api/planning/calculate`.
- API чтения сохранённых результатов:
  - список Planning Runs с `total`, `limit` и `offset`;
  - полный Planning Run по ID;
  - список уникальных магазинов для frontend dropdown;
  - operational KPI для dashboard;
  - отдельные calendar и recommendations endpoints;
  - фильтры `date_from`, `date_to` и `store_id`.
- Comparison Engine и endpoint сравнения двух Planning Runs по capacity totals.
- Notification Engine и API для urgent shortage, upcoming shortage, hiring
  deadline и staff surplus alerts.
- Explanation Context Builder для компактной передачи готовых
  расчётов в LLM.
- Ollama HTTP client с configurable URL, model, timeout и mock-тестами.
- Endpoint `POST /api/assistant/explain` с Ollama response и
  автоматическим structured fallback.
- Endpoint `GET /health/ollama` со статусами `ok`, `disabled`, `unavailable`
  и `model_missing`.
- Live-подключение FastAPI на Mac к `qwen3:8b` на Windows RTX 3080
  через Tailscale Serve; Ollama слушает localhost и недоступна из обычной
  локальной сети.
- Понятные validation issues в preview и calculate API.
- Настраиваемый CORS для разрешённых frontend origins.
- Frontend API contract в `docs/ENDPOINTS.md`.
- Автоматические тесты pytest: 63 теста проходят.
