# Заметки по backend 7X

## Полезные команды

```bash
source .venv/bin/activate
pytest
uvicorn app.main:app --reload
```

## Архитектура системы

```text
Excel demand forecast ──────────┐
Leave и workforce data ─────────┤
Календарь UAE ──────────────────┤
Исторические данные → ML ───────┤
                                ↓
                      Backend calculations
                      + Capacity Engine
                      + Recommendation Engine
                      + OR-Tools optimizer
                                |
                 ┌──────────────┴──────────────┐
                 ↓                             ↓
              Frontend                 Опциональный LLM
       структурированные данные       понятные объяснения
                 |
                 ↓
       Календарь: месяц, день или период
```

Backend является источником точных значений: количества курьеров, сроков,
приоритетов и кодов причин. Опциональный LLM может только преобразовать готовую
структурированную рекомендацию в понятный человеку текст.

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
