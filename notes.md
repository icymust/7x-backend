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

# Собрать и запустить backend + PostgreSQL одной командой
docker compose up --build -d

# Проверить состояние контейнера
docker compose ps

# Посмотреть логи PostgreSQL
docker compose logs postgres

# Посмотреть логи FastAPI и Alembic
docker compose logs -f backend

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
                                v
                         Capacity Engine
            required / available / shortage / surplus
                                |
                                v
                     Recommendation Engine
            current: rule-based permanent/outsourced 60/40
               count / deadline / priority / reason
                                |
                                v
                    Daily Summary + Calendar
                                |
                                v
                         Planning Result
              detailed plan + recommendations + calendar
                                |
                                v
                       PostgreSQL Persistence
               Dataset + immutable PlanningRun versions
                                |
               ┌────────────────┼────────────────┐
               |                |                |
               v                v                v
       Planning Run API   Derived API Engines   Comparison Engine
       details / stores   KPI / notifications   current vs baseline
       calendar / recs    90-day decision plan
               |                |                |
               └────────────────┼────────────────┘
                                |
                  ┌─────────────┴─────────────┐
                  |                           |
                  v                           v
          Structured JSON          Explanation Context Builder
                                              |
                                              v
                                     Optional Ollama LLM
                                     human-friendly text
                                              |
                                      unavailable / disabled
                                              |
                                      structured fallback
                  |                           |
                  └─────────────┬─────────────┘
                                v
                           FastAPI API
                                |
                                v
                             Frontend

Planned extensions after integration of the official dataset:

Historical forecast + actual volume → ML Forecast Corrector → Capacity Engine
Official costs and constraints → OR-Tools Workforce Optimizer → Recommendations
```

Backend является источником точных значений: количества курьеров, сроков,
приоритетов и кодов причин. Пока ML-модель не подключена, Capacity Engine
использует `forecast_volume` и DPH из Excel как baseline. Официальный Dataset
содержит `actual_volume`, поэтому после корректного importer можно провести
time-based backtest модели, которая корректирует forecast или прогнозирует
required couriers. Отдельного Workforce Optimizer сейчас нет: соотношение
60/40 является правилом Recommendation Engine. OR-Tools будет добавлен только
после появления подтверждённых ограничений и стоимости. Explanation Context
Builder собирает для выбранного дня или периода capacity, optimization status,
recommendations, daily summary и notifications. Опциональный Ollama LLM может
только превратить готовый контекст в понятный человеку текст и не участвует в
расчётах.

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
8. Rolling Decision Plan агрегирует shortage в 90-дневные workforce actions,
   не создавая отдельный найм для каждого time bucket.
9. Explanation Context Builder собирает компактный контекст выбранного дня или
   периода из capacity, optimization, recommendations, daily summary и
   notifications.
10. Ollama опционально превращает этот контекст в понятное HR-объяснение; при
   недоступности LLM возвращается структурированный fallback.
11. FastAPI отдаёт frontend подробный plan, calendar summary и explanations.

## Официальный Dataset

Файл содержит четыре листа:

- `README` — описание задания и glossary;
- `Store_Metadata` — 10 stores, location, emirate и store-level DPH;
- `Demand_Forecast` — 43 680 строк за 13 недель с шагом 30 минут;
- `Courier_Roster` — 67 couriers с типом FTE/FTC, сменой, выходным и status.

Grain листа demand: `store_id + date + time_slot`. Период данных:
`2026-04-28` — `2026-07-27`. Официальный файл задания содержит синтетические,
а не реальные operational data.

### Подтверждённое хорошее качество

- Нет null values, пустых обязательных значений и полных дубликатов.
- Ключ `store_id + date + time_slot` уникален.
- Для каждого store присутствуют все 91 день и 48 получасовых slots в день.
- Все store IDs из demand и roster находятся в `Store_Metadata`.
- `forecast_error` всегда равен `actual_volume - forecast_volume`.
- `day_name` соответствует `date`, а `is_weekend` последовательно означает
  Friday/Saturday.
- Workforce mix близок к целевому 60/40: 41 FTE и 26 FTC.
- `actual_volume` позволяет выполнить честный time-based backtest.
- `emirate`, `latitude` и `longitude` позволяют агрегировать KPI и в будущем
  искать кандидатов для transfer.

### Несоответствия README и фактического файла

- README говорит о stores в Dubai, Abu Dhabi, Sharjah, Ajman и RAK, но в
  `Store_Metadata` присутствуют только Dubai, Abu Dhabi и Sharjah.
- README описывает `max_capacity`, но такой колонки ни в одном листе нет.
- README описывает `target_utilisation_pct` как процент, но фактические
  значения равны 16–20 и не похожи на допустимый utilisation percentage.
- README упоминает courier-level `dph` и `avg_delivery_min`, но roster содержит
  только `avg_delivery_hr`; значение равно 2 у всех 67 couriers, хотя README
  говорит об индивидуальной производительности.
- `base_dph` магазина `QED_DXB_02` равен 9.0, тогда как остальные stores имеют
  значения 1.8–2.8. Это сильный outlier, который нельзя молча исправлять.
- У 16 couriers поле `working_hours` больше интервала между `shift_start` и
  `shift_end`; источник истины для длительности смены не определён.
- Status `On Leave` есть у 6 couriers, но отсутствуют `leave_from` и
  `leave_to`, поэтому неизвестен точный период недоступности.
- DPH задан за один час, а demand — за 30 минут. Capacity одного courier на
  slot должен учитывать множитель `0.5` часа.
- В Dataset нет labour cost, overtime limits, transfer limits, фактического
  on-time delivery и store closures. Соответствующие KPI и cost optimization
  нельзя честно вычислить.
- Координаты stores присутствуют, но нет допустимого travel time, transfer
  capacity и правил совместимости смен. Одних координат недостаточно для
  автоматического transfer.
- `actual_volume` и `forecast_error` являются target/evaluation data. Их нельзя
  передавать ML-модели как признаки для той же строки, иначе возникнет data
  leakage.
- Dataset использует Friday/Saturday как weekend, а текущий legacy calendar
  backend использует Saturday/Sunday и должен быть адаптирован.

До уточнения неоднозначные значения сохраняются без исправления. Любое временное
правило должно быть явно отмечено в API как assumption.

## Mapping официального Dataset

Старый `app/importers/column_mapper.py` остаётся для legacy плоского Excel,
который принимает текущий `/preview` и `/calculate`. Он ожидает, что forecast,
availability и productivity находятся на одном листе.

Новый `app/importers/workforce_mapper.py` предназначен для официального
multi-sheet файла. Он:

- распознаёт `Store_Metadata`, `Demand_Forecast` и `Courier_Roster`;
- игнорирует информационный лист `README`;
- переводит исходные названия в canonical backend names;
- разделяет core-поля для расчёта и дополнительные поля для ML/evaluation;
- сообщает о пропущенных рабочих листах и обязательных колонках.

`app/importers/workforce_loader.py` читает workbook целиком, применяет mapping и
возвращает три нормализованных DataFrame: `store_metadata`, `demand_forecast` и
`courier_roster`. Loader проверяет, что Excel читается, обязательные листы и
core-колонки существуют, а mapping не создаёт повторяющиеся canonical columns.

Loader пока не объединяет листы, не рассчитывает capacity и не подключён к API.
`app/importers/workforce_validator.py` отдельно проверяет null values, ключи,
числа, даты, 30-минутные slots, forecast consistency, FTE/FTC, courier status,
weekly off, shift times и cross-sheet store integrity. Блокирующие проблемы
возвращаются в `errors`, а неоднозначные данные — в `warnings`.

На официальном XLSX validator возвращает `is_valid: true`, `0 errors` и четыре
группы warnings:

- один store-level productivity outlier (`QED_DXB_02`);
- suspicious target utilization для всех 10 stores;
- `working_hours` превышает shift window у 16 couriers;
- отсутствует leave period у 6 couriers со status `On Leave`.

## Что уже сделано в backend

- FastAPI-приложение со Swagger и endpoint `/health`.
- Health endpoints для PostgreSQL и опциональной Ollama-модели.
- Загрузка `.xlsx` и preview листов, колонок и первых строк.
- Нормализация названий колонок и mapping aliases во внутренний формат backend.
- Mapping и multi-sheet loader официального workforce Dataset.
- Workforce validator для трёх листов и cross-sheet связей.
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
  - UAE weekend metadata и подготовленные поля public holiday;
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
- Rolling Decision Plan Engine и 90-дневный API с агрегированными emergency,
  outsourced и permanent actions; transfer/overtime stages ожидают официальные
  operational data.
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
- Dockerfile и Compose для запуска FastAPI + PostgreSQL одной командой;
  Alembic автоматически применяет миграции перед Uvicorn.
- Frontend API contract в `docs/ENDPOINTS.md`.
- Автоматические тесты pytest: 85 тестов проходят.
