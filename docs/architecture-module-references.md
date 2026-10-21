# Архитектура модуля references

Модуль `references` владеет **общесистемными справочными данными**, которые нужны
нескольким модулям и не принадлежат ни одному домену. Он фундаментальный: `core`
и `operations` зависят от него. Решение и обоснование — в
`docs/adr/0017-references-module.md`.

## Назначение

- **Справочник валют (ISO 4217).** Полный список действующих кодов с числовым
  кодом, символом и минорными единицами; названия переводятся (ADR 0016).
- **Типы курсов.** Банковские типы курсов, каждый опирается на один из
  фиксированных принципов (см. ниже).

Валюты и типы курсов адресуются **по коду**; другие модули хранят код строкой, а
не внешним ключом в чужую таблицу (инвариант «данные принадлежат модулю»).

## Публичный контракт

Модуль публикует в реестре (`modules.common.contracts.registry`) один сервис:

- `references.directory` (`ReferenceDirectory`) — чтение словаря валют
  (`currencies`, `get_currency`) и типов курсов (`rate_types`, `get_rate_type`).
- `references.rate_type_usage_guard` (`RateTypeUsageGuard`) — необязательный
  callback, который реализует владелец курсов (`core`) и который сообщает,
  можно ли ещё менять `validity` типа. Так `references` не обращается к таблицам
  `core`.

Провансер `ReferenceDirectory` реализован в `modules.references.backend.services`.
Конфигурация валют кассы и курсы остаются в контракте `core.cash_desk_config`.

## Схема данных

Схема PostgreSQL — `references`.

```mermaid
erDiagram
    CURRENCY {
        bigint id PK
        string code UK
        string numeric_code
        string name
        string symbol
        int minor_units
        bool is_active
    }
    CURRENCY_TRANSLATION {
        bigint id PK
        bigint currency_id FK
        string language
        string name
    }
    CURRENCY_RATE_TYPE {
        bigint id PK
        string code UK
        string name
        string principle
        string validity
        bool daily_required
        bool is_system
        bool is_active
        int order
    }
    CURRENCY_RATE_TYPE_TRANSLATION {
        bigint id PK
        bigint rate_type_id FK
        string language
        string name
    }
    CURRENCY ||--o{ CURRENCY_TRANSLATION : translated
    CURRENCY_RATE_TYPE ||--o{ CURRENCY_RATE_TYPE_TRANSLATION : translated
```

## Типы курсов: принцип и банковский тип

- **Принцип** — фиксированный набор констант в контракте
  (`CurrencyRatePrinciple`): `official` (курс Нацбанка), `buy`, `sell`,
  `conversion`. На принцип опирается код операций, поэтому он задан в коде, а не
  данными (по образцу `OperationKind`).
- **Банковский тип** (`CurrencyRateType`) — управляемый банком справочник: у него
  произвольное название и ссылка на принцип. Банк может завести несколько типов
  одного принципа (например «Покупка наличных» и «Покупка безнал»). Системные
  типы поставляются и не удаляются через API: `official`, `buy`, `sell`,
  `conversion`, а также `conversion_buy` и `conversion_sell` — две стороны
  прямой пары конверсии (см. `docs/architecture-module-core.md`).
- **Действие курса** (`validity`) — `calendar_day` (один действующий курс на
  календарный день и область) или `since_set` (курс действует с указанных даты и
  времени). По умолчанию у принципа `official` — `calendar_day`, у остальных —
  `since_set`. Признак нельзя изменить, пока у типа есть хотя бы один курс
  (проверка через callback-контракт `RateTypeUsageGuard`, который реализует
  модуль `core`, владеющий курсами).
- **Требуется ежедневно** (`daily_required`) — если включён, при операции должен
  существовать курс на дату операции; если выключен, берётся последнее значение
  на момент операции. По умолчанию включён только для `official`.

Курсы (`core.CurrencyRate`) ссылаются на **банковский тип** по коду; принцип и
признаки действия берутся из типа. Выбор и пересчёт по принципу в операциях —
следующая итерация.

## Наполнение валют

Справочник наполняется полным списком действующих кодов ISO 4217 командой
`seed_iso_currencies` из статического датасета `backend/catalogue/iso4217.py`. Команда
идемпотентна. Внешняя загрузка (обновление из провайдера) — отдельная будущая
работа.

## Права

- `references.view` — чтение справочников;
- `references.manage` — изменение (создание, правка, удаление).

Каталог прав собирается агрегацией по модулям (ADR 0012).

## Связанные документы

- `docs/adr/0017-references-module.md` — решение о модуле и справочниках.
- `docs/adr/0016-translatable-reference-data.md` — переводы названий.
- `docs/architecture-module-core.md` — конфигурация валют кассы и курсы.
- `docs/api.md` — REST API справочников.
