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

# Оценить качество исходного forecast на official Dataset
python scripts/evaluate_forecast_baseline.py \
  "real_data/Dataset_AI-Powered Workforce Planning & Capacity Intelligence_Final.xlsx"

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
            Daily aggregation: store_id + date
       daily orders + store metadata + FTE/FTC hours
                                |
                                v
                     CatBoost Demand Forecast
          historical correction or 90-day future forecast
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

Current decision flow:

Historical actual demand → CatBoost future forecast → Predicted Demand
Predicted Demand + Current Workforce → Workforce Gap
Workforce Gap → Rolling Decision Plan → Ollama explanation
```

Backend является источником точных значений: количества курьеров, сроков,
приоритетов и кодов причин. Для historical flow CatBoost корректирует
`forecast_volume` из Excel. Для даты после конца истории отдельная модель
строит 90 будущих store-days на основе недельного baseline и прошлых demand.
После этого Capacity Engine рассчитывает workforce gap. Если модель недоступна,
используется соответствующий baseline. Отдельного Workforce Optimizer сейчас
нет: соотношение 60/40 является правилом Recommendation Engine. OR-Tools будет
добавлен только после появления подтверждённых ограничений и стоимости.
Explanation Context Builder собирает capacity, recommendations, daily summary,
notifications и rolling decision actions. Ollama только объясняет этот готовый
контекст и не участвует в расчётах.

## Основной flow

1. Пользователь загружает Excel с forecast, workforce и leave.
2. Backend читает файл, сопоставляет колонки и валидирует значения.
3. CatBoost корректирует `forecast_volume` по историческим `actual_volume`,
   store и временным признакам. Если `planning_date` позже истории, backend
   формирует 90 новых дней; weekly seasonal forecast остаётся fallback.
4. Capacity Engine рассчитывает required, effective available, shortage и
   surplus по каждому store/time bucket.
5. Decision Engine формирует только выполнимые варианты действий: transfer,
   overtime, FTC, FTE или их комбинацию. Текущий fallback использует mix 60/40.
6. Rule-based scoring ранжирует варианты по coverage, сроку готовности,
   стоимости и риску и возвращает до трёх рекомендаций.
7. Для выбранных рекомендаций backend формирует количество, deadline, priority
   и reason.
8. Daily Summary группирует результат по дням для календаря.
9. Rolling Decision Plan агрегирует shortage в 90-дневные workforce actions,
   не создавая отдельный найм для каждого time bucket.
10. Explanation Context Builder собирает компактный контекст выбранного дня или
   периода из capacity, recommendations, daily summary, notifications и
   rolling decision plan.
11. Ollama опционально превращает этот контекст в понятное HR-объяснение; при
   недоступности LLM возвращается структурированный fallback.
12. FastAPI отдаёт frontend подробный plan, recommendation cards, calendar
    summary и explanations.

## Целевые recommendation cards

После расчёта workforce gap система должна возвращать от одной до трёх карточек
с разными полезными компромиссами:

- `best_overall` — лучший баланс coverage, срока, стоимости и риска;
- `lowest_cost` — самый дешёвый из выполнимых вариантов;
- `fastest` — вариант с минимальным временем готовности.

Карточка может комбинировать действия, например transfer нескольких couriers и
добавление FTC. Она содержит actions, ожидаемый `coverage_percent`,
`cost_level`, `risk_level`, `ready_in`, reason и покрываемый период. Backend не
обязан возвращать ровно три карточки: если выполним только один честный вариант,
возвращается одна рекомендация без искусственных альтернатив.

На первом этапе ranking остаётся rule-based и объяснимым. Coverage считается из
capacity plan, readiness — из подтверждённых lead times, а cost/risk используют
явную business configuration. Значения нельзя выдавать как точные, если для них
нет подтверждённых входных данных. Отдельный ML Ranking Model возможен только
после накопления истории выбранных менеджером вариантов и фактических outcomes.
Выбор карточки делает менеджер; сохранение этого выбора потребует отдельного API
и станет источником данных для будущего ranking model.

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
- Dataset использует Friday/Saturday как weekend. Official calculation передаёт
  это значение в calendar; legacy flow сохраняет Saturday/Sunday default.

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

`app/importers/workforce_normalizer.py` принимает проверенные три DataFrame.
Он сохраняет получасовые canonical rows для возможного будущего анализа, а для
основного MVP дополнительно собирает daily rows с grain `store_id + date`:

- объединяет `date + time_slot` в `time_bucket`;
- сохраняет длительность каждого slot как `0.5` часа;
- присоединяет store name, emirate, zone, coordinates и raw store productivity;
- суммирует forecast и actual за все интервалы дня;
- считает FTE как permanent, а FTC как outsourced;
- вычисляет shift end как `shift_start + 9h` для FTE или `shift_start + 11h`
  для FTC и учитывает overnight shifts;
- учитывает weekly off и status `On Leave`;
- сохраняет actual volume и forecast error только для будущего ML/backtest.

В daily rows один courier учитывается один раз за день. Его доступная мощность
равна 8 рабочим часам для FTE или 10 для FTC. Получасовая shift availability не
используется основным MVP.

Для MVP официальный расчёт использует суточный grain:

- одна строка plan = один магазин + один день;
- 48 исходных получасовых строк суммируются в дневное количество заказов;
- `On Leave` считается недоступным на всём горизонте, потому что дат отпуска
  нет;
- weekly off исключает курьера из доступности в соответствующий день;
- распределение людей внутри смены оставлено менеджеру.

Полный официальный файл превращается из 43 680 строк demand в 910 дневных строк:
10 stores × 91 день. Исходные получасовые данные остаются в Excel и могут быть
использованы позже, но основной MVP их не показывает.

## Формулы официального Dataset

Официальный Excel не содержит готового staffing plan. Он предоставляет demand,
store productivity и courier roster. Backend последовательно получает из них
следующие значения.

### Суточная агрегация спроса

```text
daily_forecast_orders = sum(forecast_shipments по store_id и date)
daily_actual_orders = sum(actual_shipments по store_id и date)
```

ML и dashboard работают с дневным количеством заказов. `actual_shipments`
используется как historical target для ML, а не как известное будущее значение.

### Доступность workforce

Для каждого магазина и дня считаются уникальные FTE и FTC:

```text
effective_FTE = all FTE - weekly off - On Leave
effective_FTC = all FTC - weekly off - On Leave

available_courier_hours = effective_FTE × 8 + effective_FTC × 10
available_delivery_capacity = available_courier_hours × 2
```

Один FTE может выполнить примерно 16 заказов в день, один FTC — 20. Час break
не входит в 8/10 рабочих часов.

### Требуемое количество и дефицит

В official `/calculate` используется простая формула:

```text
required_courier_hours = daily_forecast_orders / 2

average_working_hours = 8 × 60% + 10 × 40% = 8.8
required_couriers = ceil(required_courier_hours / 8.8)

shortage_hours = max(required_courier_hours - available_courier_hours, 0)
surplus_hours = max(available_courier_hours - required_courier_hours, 0)

shortage = ceil(shortage_hours / 8.8)
surplus = floor(surplus_hours / 8.8)
```

Это прозрачный MVP-расчёт, а не оптимизация смен. Target mix 60/40 используется
только для перевода требуемых часов в приблизительное количество людей.

`actual_shipments` и `forecast_error` не участвуют в расчёте будущего staffing:
они используются только для обучения и проверки ML.

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

Текущие операционные KPI для official daily plan:

```text
required_courier_hours = sum(required_courier_hours)
available_courier_hours = sum(available_courier_hours)
covered_hours = min(required_courier_hours, available_courier_hours)
coverage_percent = covered_hours / required_courier_hours × 100
```

- `coverage_percent` — какая доля требуемой courier capacity покрыта;
- `understaffed_buckets` — сколько store-days имеют shortage;
- `balanced_buckets` — сколько store-days закрыто без shortage и surplus;
- `overstaffed_buckets` — сколько store-days имеют surplus;
- `affected_stores` — сколько stores сталкиваются с дефицитом;
- `critical_days` — дни, где shortage не менее 20% required capacity либо
  существует recommendation с priority `critical`;
- `emergency_hiring_actions` — количество store-days, которым требуется
  emergency outsourcing.

Старые поля `*_courier_slots` временно сохранены для обратной совместимости API,
но в official flow каждая строка уже соответствует одному store-day.

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

## ML preparation и forecast baseline

`app/ml/demand_features.py` собирает training DataFrame напрямую из проверенного
multi-sheet workbook. Отдельный CSV не создаётся. Grain — `store_id + date`,
target — дневная сумма `actual_shipments`.

Признаки: store, emirate, zone, weekday, month, Friday/Saturday weekend,
дневная сумма исходного forecast, lag actual за предыдущий день и rolling mean
за 7/28 прошлых дней. Перед rolling применяется `shift(1)`, поэтому будущие
actual values не попадают в признаки.

`split_training_data_by_time` оставляет последние 20% дат для test и не
перемешивает строки случайно. `scripts/evaluate_forecast_baseline.py` сравнивает
исходный `forecast_shipments` с `actual_shipments` через MAE, bias и WAPE.

Результат official Dataset:

```text
train: 2026-04-28 — 2026-07-08, 720 store-days
test:  2026-07-09 — 2026-07-27, 190 store-days
test MAE: 6.0842 deliveries per store-day
test bias: 0.9579 (actual - forecast)
test WAPE: 1.8982%
```

`CatBoostRegressor` обучается как residual correction: исходный forecast
остаётся сильным baseline, а модель прогнозирует его поправку. Категориальные
признаки `store_id`, `emirate` и `zone` передаются CatBoost напрямую.

Команда обучения:

```bash
cd backend
python scripts/train_demand_model.py \
  "real_data/Dataset_AI-Powered Workforce Planning & Capacity Intelligence_Final.xlsx"
```

Честный backtest на тех же последних 19 днях:

```text
Excel baseline: MAE 6.0842, WAPE 1.8982%
CatBoost:       MAE 6.0630, WAPE 1.8916%
WAPE improvement: 0.0066 percentage points
```

Улучшение небольшое, но измеримое. Финальная модель после backtest переобучена
на всех 910 historical store-days и сохранена как
`model_artifacts/demand_forecast.cbm`. Dataset синтетический, поэтому метрики не
гарантируют production accuracy.

Official `/calculate` загружает готовую модель и для каждого store-day
возвращает:

```text
baseline_forecast_shipments = исходный прогноз Excel
predicted_shipments = baseline + CatBoost correction
planning_demand_shipments = значение, по которому backend считает couriers
prediction_source = catboost
```

Если модель отсутствует или несовместима, `predicted_shipments` становится
равным Excel forecast, а `prediction_source` — `excel_baseline`. Повторное
обучение при загрузке Excel не запускается.

### Future forecast на 90 дней

Если `planning_date` позже `2026-07-27`, official `/calculate` создаёт ровно 90
будущих дней для каждого магазина. Например, для `planning_date=2026-08-05`
результат содержит 900 строк: 10 stores × 90 дней, период до `2026-11-02`.

Future baseline повторяет последний доступный недельный паттерн исходного Excel
forecast. `catboost-daily-future-v1` прогнозирует поправку к этому baseline по
store, emirate, zone, calendar и leakage-safe lag/rolling demand features.
Пропущенные дни между концом истории и `planning_date` рассчитываются
рекурсивно, но в API возвращается только выбранный 90-дневный горизонт.

Честный recursive backtest на последних 19 днях:

```text
Seasonal baseline: MAE 8.3526, WAPE 2.6060%
Future CatBoost:   MAE 8.1900, WAPE 2.5552%
WAPE improvement: 0.0508 percentage points
```

Будущие строки не содержат `actual_shipments`: фактический спрос на них ещё не
известен. Availability экстраполируется из текущего roster, weekly off и
статуса leave. Это MVP-допущение, поскольку даты отпусков в Dataset отсутствуют.

## Что уже сделано в backend

- FastAPI-приложение со Swagger и endpoint `/health`.
- Health endpoints для PostgreSQL и опциональной Ollama-модели.
- Загрузка `.xlsx` и preview листов, колонок и первых строк.
- Multi-sheet preview официального workbook с отдельными результатами для
  `Store_Metadata`, `Demand_Forecast` и `Courier_Roster`.
- Нормализация названий колонок и mapping aliases во внутренний формат backend.
- Mapping и multi-sheet loader официального workforce Dataset.
- Workforce validator для трёх листов и cross-sheet связей.
- Workforce normalizer сохраняет исходные 30-минутные строки и формирует
  основной daily plan: FTE/FTC, 8/10 рабочих часов, weekly off и leave.
- CatBoost daily demand model обучена и проверена относительно Excel baseline.
- CatBoost подключена к official `/calculate` с безопасным Excel fallback.
- Future CatBoost формирует 90 новых дней после конца Excel с безопасным
  seasonal fallback.
- Rolling actions содержат проверяемый `evidence`: baseline/ML demand,
  model source, peak required/available и shortage до действия.
- Горизонт `one_week_to_one_month` однозначно означает дни `4–29`, а не
  фиксированную недельную длительность action.
- Каждое rolling action имеет стабильный `action_id`; frontend передаёт его в
  `/api/assistant/explain`, чтобы получить объяснение одной выбранной карточки.
- Ollama получает summary всех actions и сбалансированные примеры каждого
  горизонта; она только переводит evidence в короткое объяснение.
- Валидация пропусков, дат, чисел, отрицательных значений, productivity,
  дубликатов store/time и количества недоступных курьеров.
- Генератор искусственного Excel для работы до получения официального файла.
- Расчёт capacity для каждого магазина и временного интервала:
  - required couriers;
  - available couriers;
  - shortage и surplus;
  - настраиваемый target utilization для legacy flow и фиксированный `1.0` для
    official flow;
  - отсутствующие permanent и outsourced из-за отпуска или выходного.
- Endpoint `POST /api/planning/calculate` для legacy и официального multi-sheet
  Excel с сохранением `Dataset` и `PlanningRun`.
- Official planning result содержит `store_name`, `emirate`, `zone`, validation
  warnings, normalization assumptions и `model_version`.
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
- ML training-data builder с leakage-safe lag/rolling features и time split.
- CLI для оценки forecast baseline по MAE, bias и WAPE.
- Автоматические тесты pytest: 114 тестов проходят.

