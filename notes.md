# Заметки по backend 7X

## Полезные команды

```bash
# Активировать виртуальное окружение Python
source backend/.venv/bin/activate

# Перейти в backend для Python-команд
cd backend

# Запустить backend в режиме разработки
uvicorn app.main:app --reload

# Запустить все тесты
pytest

# Вернуться в корень monorepo для Docker-команд
cd ..

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

# Снова перейти в backend для Alembic-команд
cd backend

# Показать текущую версию миграции
alembic current

# Сгенерировать миграцию после изменения models
alembic revision --autogenerate -m "migration description"

# Применить все новые миграции
alembic upgrade head
```

## Структура monorepo

```text
repository/
├── backend/       # FastAPI, tests, Alembic и Python dependencies
├── frontend/      # frontend-приложение добавляется отдельно
├── docs/          # общая документация и API contract
├── compose.yaml   # общий запуск сервисов
├── .env.example
└── .gitignore
```

Python-команды (`pytest`, `uvicorn`, `alembic`) выполняются из `backend/`.
Docker Compose запускается из корня repository.

## Архитектура системы

```text
                         Excel от 7X
             demand forecast + workforce + leave
                                |
                                v
             Import → Mapping → Validation → Normalization
                                |
                                v
             30-minute canonical capacity rows
       demand + store metadata + FTE/FTC availability
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

Ответы recruiters из `docs/7x hackathon questions .pdf` считаются более
приоритетным business source, чем противоречащие им значения синтетического
Excel. Подтверждено:

- capacity одного courier — 2 deliveries в час или 1 delivery за 30 минут;
- FTE — 8 рабочих часов плюс 1 час break;
- FTC — 10 рабочих часов плюс 1 час break;
- целевой workforce mix — 60% FTE и 40% FTC;
- FTE cost — 4000 AED/month, FTC cost — 4500 AED/month;
- расчётный месяц — 26 дней, revenue — 11.5 AED за completed delivery;
- transfer занимает 1–3 дня и предпочтителен внутри одного emirate;
- external drivers доступны за 2–5 дней;
- нужны short-term и long-term recommendations с данными и объяснением.

Главный optimization priority между shortage, service и cost пока не
подтверждён.

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
- Все FTE соответствуют правилу `8+1`, но только 3 из 26 FTC имеют source shift
  window 11 часов. У 16 FTC `working_hours` даже больше source shift window.
  Normalizer доверяет recruiter rule и вычисляет shift end из `shift_start`;
  исходный `shift_end` сохраняется только для validation warning.
- Status `On Leave` есть у 6 couriers, но отсутствуют `leave_from` и
  `leave_to`, поэтому неизвестен точный период недоступности.
- После применения recruiter shift rule остаётся 13 795 slots с положительным
  forecast без scheduled courier; это 13.8% forecast volume. Нужны operating
  hours или дополнительные ночные shifts, иначе shortage останется высоким.
- Recruiter подтвердил DPH = 2 deliveries/hour. Для 30-минутного demand slot
  capacity одного courier равна `2 × 0.5 = 1 delivery`.
- В Excel нет labour cost, но salary и revenue подтверждены отдельно recruiters
  и хранятся как business configuration. Overtime limits, фактический on-time
  delivery и store closures всё ещё отсутствуют.
- Координаты stores присутствуют, но нет допустимого travel time, transfer
  capacity и правил совместимости смен. Одних координат недостаточно для
  автоматического transfer.
- `actual_volume` и `forecast_error` являются target/evaluation data. Их нельзя
  передавать ML-модели как признаки для той же строки, иначе возникнет data
  leakage.
- Dataset использует Friday/Saturday как weekend, а текущий legacy calendar
  backend использует Saturday/Sunday и должен быть адаптирован.

Противоречащие значения Excel не исправляются внутри исходного файла. Backend
сохраняет их для аудита, применяет подтверждённые recruiter rules и возвращает
соответствующие warnings/assumptions.

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

Сам loader не объединяет листы и не рассчитывает capacity.
`app/importers/workforce_validator.py` отдельно проверяет null values, ключи,
числа, даты, 30-минутные slots, forecast consistency, FTE/FTC, courier status,
weekly off, shift times и cross-sheet store integrity. Блокирующие проблемы
возвращаются в `errors`, а неоднозначные данные — в `warnings`.

На официальном XLSX validator возвращает `is_valid: true`, `0 errors` и пять
групп warnings:

- один store-level productivity outlier (`QED_DXB_02`);
- suspicious target utilization для всех 10 stores;
- source shift window не соответствует recruiter rule у 23 FTC;
- `working_hours` превышает shift window у 16 couriers;
- отсутствует leave period у 6 couriers со status `On Leave`.

`POST /api/datasets/preview` распознаёт официальный workbook, если в нём есть
рабочие листы workforce-формата. Для каждого из трёх листов response содержит:

- исходное и canonical название листа;
- исходные колонки и применённый column mapping;
- canonical columns и общее количество строк;
- не более пяти нормализованных строк для интерфейса;
- общие validation `errors` и `warnings` по всему workbook.

Preview проверяет полный Dataset, но не сохраняет его в PostgreSQL, не запускает
normalizer и не считает capacity. Если отсутствует обязательный лист или
core-колонка, validation становится невалидной. Warnings не блокируют следующий
этап. Старый плоский Excel остаётся совместимым и использует legacy preview.

`app/importers/workforce_normalizer.py` принимает проверенные три DataFrame и
собирает единые capacity rows с grain `store_id + time_bucket`. Он:

- объединяет `date + time_slot` в `time_bucket`;
- сохраняет длительность каждого slot как `0.5` часа;
- присоединяет store name, emirate, zone, coordinates и raw store productivity;
- применяет recruiter capacity `2 deliveries/hour × 0.5 = 1 delivery/slot`;
- считает FTE как permanent, а FTC как outsourced;
- вычисляет shift end как `shift_start + 9h` для FTE или `shift_start + 11h`
  для FTC и учитывает overnight shifts;
- учитывает weekly off и status `On Leave`;
- сохраняет actual volume и forecast error только для будущего ML/backtest.

Для совместимости с Capacity Engine поля `available_permanent` и
`available_outsourced` означают couriers, смена которых покрывает slot. Поля
`permanent_unavailable` и `outsourced_unavailable` содержат находящихся среди
них на weekly off или `On Leave`. Поэтому effective availability будет
рассчитана ровно один раз внутри Capacity Engine.

Временные assumptions normalizer возвращает явно:

- recruiter shift duration важнее конфликтующего source `shift_end`;
- вычисленный shift end не включается в смену;
- один час break пока не назначается конкретным slots, потому что break schedule
  отсутствует;
- из-за отсутствия leave dates status `On Leave` действует на весь горизонт;
- capacity slot использует подтверждённую productivity `1 delivery`;
- official target utilization равен `1.0`, а подозрительный raw
  `target_utilization_percent` сохраняется только как metadata.

Проверка полного официального файла дала 43 680 capacity rows, 10 stores и
период `2026-04-28 00:00` — `2026-07-27 23:30`. Loader и validator подключены к
`/preview`; normalizer пока не подключён к `/calculate`.

## Формулы официального Dataset

Официальный Excel не содержит готового staffing plan. Он предоставляет demand,
store productivity и courier roster. Backend последовательно получает из них
следующие значения.

### Нормализация временного интервала

```text
time_bucket = date + time_slot
time_bucket_hours = 30 / 60 = 0.5
productivity_per_courier = 2 deliveries/hour × 0.5 = 1 delivery
official_target_utilization = 1.0
```

`productivity_per_courier` показывает, сколько доставок один courier способен
выполнить за один 30-минутный slot. Recruiters подтвердили это значение, поэтому
store-level `base_dph` сохраняется для аудита/ML, но не управляет staffing.

### Доступность workforce

Для каждого courier normalizer берёт `shift_start`, затем по recruiter rule
вычисляет конец присутствия:

```text
FTE shift end = shift_start + 8 work hours + 1 break hour
FTC shift end = shift_start + 10 work hours + 1 break hour
```

После этого для каждого store и time bucket считаются couriers, чья вычисленная
смена покрывает интервал:

```text
available_permanent = количество FTE внутри shift interval
available_outsourced = количество FTC внутри shift interval

permanent_unavailable = FTE внутри смены с weekly off или On Leave
outsourced_unavailable = FTC внутри смены с weekly off или On Leave

effective_permanent = available_permanent - permanent_unavailable
effective_outsourced = available_outsourced - outsourced_unavailable
available_couriers = effective_permanent + effective_outsourced
```

Несмотря на название, `available_permanent/outsourced` здесь означает
запланированный roster внутри смены до вычета отсутствующих. Это сохраняет
совместимость с существующим Capacity Engine.

### Требуемое количество и дефицит

После подключения official normalizer к `/calculate` существующий Capacity
Engine будет применять:

```text
required_couriers = ceil(
    forecast_shipments
    / productivity_per_courier
    / target_utilization
)

capacity_gap = available_couriers - required_couriers
shortage = max(required_couriers - available_couriers, 0)
surplus = max(available_couriers - required_couriers, 0)
```

Для official flow `productivity_per_courier = 1` и
`target_utilization = 1.0`, поэтому формула упрощается:

```text
required_couriers = ceil(forecast_shipments)
```

Неподтверждённый buffer `0.85` не применяется. Значения
`target_utilisation_pct = 16–20` из Excel остаются raw metadata.

`actual_shipments` и `forecast_error` не участвуют в расчёте staffing для той же
строки: это было бы target leakage. Они используются только для оценки качества
forecast и будущего time-based ML backtest.

### Recommendation Engine

Текущий fallback использует временное правило 60% permanent / 40% outsourced:

```text
target_permanent = ceil(required_couriers × 0.60)
target_outsourced = required_couriers - target_permanent
permanent_gap = max(target_permanent - effective_permanent, 0)
add_permanent = min(shortage, permanent_gap)
add_outsourced = shortage - add_permanent
```

Permanent hiring за 60 дней пока остаётся MVP assumption. Recruiters
подтвердили external drivers lead time 2–5 дней, поэтому временное значение 10
дней в Recommendation Engine ещё нужно заменить. Это rule-based MVP, а не
результат ML или cost optimization.

## KPI: что считаем и зачем

KPI не берутся готовыми из Excel. `GET /api/planning-runs/{id}/kpis` агрегирует
уже рассчитанные capacity rows выбранного Planning Run, магазина и периода.

Текущие операционные KPI:

```text
required_courier_slots = sum(required_couriers)
available_courier_slots = sum(available_couriers)
shortage_courier_slots = sum(shortage)
surplus_courier_slots = sum(surplus)

covered_slots = sum(min(required_couriers, available_couriers))
coverage_percent = covered_slots / required_courier_slots × 100
```

- `coverage_percent` — какая доля требуемой courier capacity покрыта;
- `understaffed_buckets` — сколько временных интервалов имеют shortage;
- `balanced_buckets` — сколько интервалов закрыто без shortage и surplus;
- `overstaffed_buckets` — сколько интервалов имеют surplus;
- `affected_stores` — сколько stores сталкиваются с дефицитом;
- `critical_days` — дни, где shortage не менее 20% required capacity либо
  существует recommendation с priority `critical`;
- `emergency_hiring_actions` — количество time buckets, которым требуется
  emergency outsourcing.

Суммы `*_courier_slots` не являются количеством уникальных couriers: один
courier может учитываться в нескольких 30-минутных slots. Для решения «сколько
людей одновременно нужно» используются bucket-level значения и maximum
shortage, а не сумма за день или месяц.

Из `forecast_shipments` и `actual_shipments` также реально добавить KPI качества
прогноза:

```text
forecast_error = actual_shipments - forecast_shipments
MAE = mean(abs(forecast_error))
bias = mean(forecast_error)
WAPE = sum(abs(forecast_error)) / sum(actual_shipments) × 100
```

Эти показатели нужны, чтобы доказать измеримое улучшение ML относительно
исходного forecast. Они ещё не добавлены в текущий KPI endpoint.

Главные KPI для MVP: `coverage_percent`, доля understaffed buckets и forecast
WAPE. `surplus_courier_slots` нужен как guardrail, чтобы система не улучшала
coverage простым избыточным наймом.

Salary и revenue отсутствуют в XLSX, но подтверждены recruiters и позволяют
добавить базовые cost/revenue KPI через business configuration. Пока нельзя
честно рассчитать overtime cost, on-time delivery/SLA и фактическую
эффективность transfers: соответствующие данные отсутствуют.

## Что уже сделано в backend

- FastAPI-приложение со Swagger и endpoint `/health`.
- Health endpoints для PostgreSQL и опциональной Ollama-модели.
- Загрузка `.xlsx` и preview листов, колонок и первых строк.
- Multi-sheet preview официального workbook с отдельными результатами для
  `Store_Metadata`, `Demand_Forecast` и `Courier_Roster`.
- Нормализация названий колонок и mapping aliases во внутренний формат backend.
- Mapping и multi-sheet loader официального workforce Dataset.
- Workforce validator для трёх листов и cross-sheet связей.
- Workforce normalizer для 30-минутных capacity rows, shift availability,
  FTE/FTC, weekly off и leave.
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
- Автоматические тесты pytest: 92 теста проходят.
