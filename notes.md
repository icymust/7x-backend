# Заметки по backend 7X

## Полезные команды

```bash
source .venv/bin/activate
pytest
uvicorn app.main:app --reload
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
   deliveries per courier                 |
              |                           |
              └─────────────┬─────────────┘
                            v
                     Capacity Engine
           required / available / shortage / surplus
                            |
                            v
                  OR-Tools optimizer
              permanent / outsourced / cost
                            |
                            v
                Recommendation Engine
          count / deadline / priority / reason
                            |
              ┌─────────────┴─────────────┐
              |                           |
              v                           v
     Daily Summary + Calendar       Опциональный Ollama LLM
     month / day / date range       только объясняет результат
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
исторических данных ML будет предсказывать это значение. Опциональный Ollama
LLM может только преобразовать готовую структурированную рекомендацию в понятный
человеку текст и не участвует в расчётах.

## Основной flow

1. Пользователь загружает Excel с forecast, workforce и leave.
2. Backend читает файл, сопоставляет колонки и валидирует значения.
3. Productivity берётся из Excel или предсказывается ML-моделью при наличии
   обученной модели и подходящих исторических данных.
4. Capacity Engine рассчитывает required, effective available, shortage и
   surplus по каждому store/time bucket.
5. OR-Tools подбирает permanent/outsourced mix с учётом сроков, стоимости и
   ограничений. До его подключения используется rule-based mix 60/40.
6. Recommendation Engine формирует количество, deadline, priority и reason.
7. Daily Summary группирует результат по дням для календаря.
8. Ollama опционально превращает готовую рекомендацию в понятное HR-объяснение;
   при недоступности LLM возвращается структурированный fallback.
9. FastAPI отдаёт frontend подробный plan, calendar summary и explanations.

## Что уже сделано в backend

- FastAPI-приложение со Swagger и endpoint `/health`.
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
- Автоматические тесты pytest: 19 тестов проходят.
