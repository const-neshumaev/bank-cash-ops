# REST API

Базовый префикс: `/api/`. Формат данных — JSON. Интерактивная документация
(Swagger UI) доступна по адресу `/api/docs/`, схема OpenAPI — `/api/schema/`.

Аутентификация — JWT. Для защищённых методов передавайте заголовок:

```
Authorization: Bearer <access_token>
```

Язык ответа определяется заголовком `Accept-Language` (`ru` или `en`); при его
отсутствии используется язык по умолчанию банка (см.
`docs/adr/0015-application-language-layers.md`). Выбор языка конкретного
пользователя хранится в поле `language` его профиля.

Названия справочных данных (валюты, типы операций и их слоты) также отдаются на
языке запроса; базовые значения хранятся на русском, переводы — в отдельных
таблицах модуля-владельца, при отсутствии перевода отдаётся базовое значение (см.
`docs/adr/0016-translatable-reference-data.md`).

## Настройки банка (`/api/settings/`)

| Метод | Путь | Доступ | Описание |
| --- | --- | --- | --- |
| GET | `/api/settings/` | публичный | Языки, национальная валюта и тип конверсии: `{ "default_language", "enabled_languages", "base_currency", "conversion_mode" }` |
| PATCH | `/api/settings/` | `core.bank_settings.manage` | Изменить настройки, например `{ "base_currency": "BYN", "conversion_mode": "direct" }` |

Публичный GET: SPA читает его до входа, чтобы показать экран входа на языке
по умолчанию банка. `language` в профиле валидируется по `enabled_languages`, а
`base_currency` — по активным валютам справочника `references`.

`conversion_mode` задаёт способ пересчёта между валютами:

- `via_base` (по умолчанию) — курсы конверсии задаются к национальной валюте,
  пересчёт идёт через неё;
- `direct` — можно задавать прямые пары, например `EUR/USD`.

Смена `base_currency` запрещена, пока в системе есть курсы или базовые величины
в другой валюте: это защищает исторические данные от переинтерпретации. Режим
`conversion_mode` можно менять; прямые курсы остаются в журнале, но в режиме
`via_base` не участвуют в разрешении и не показываются в текущих курсах.

## Базовые величины (`/api/base-values/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/base-values/` | `core.base_values.view` | Справочник базовых величин |
| POST | `/api/base-values/` | `core.base_values.manage` | Добавить величину |
| PATCH | `/api/base-values/{id}/` | `core.base_values.manage` | Изменить будущую величину |
| DELETE | `/api/base-values/{id}/` | `core.base_values.manage` | Удалить будущую величину |

Запись содержит `effective_from` (дата начала действия), `amount` и
`currency_code`. `currency_code` — снимок национальной валюты на момент создания,
поэтому в запросе не передаётся. Дата уникальна; будущие записи можно менять и
удалять, уже вступившие в силу — нельзя (append-only).

## Служебные методы

| Метод | Путь | Доступ | Описание |
| --- | --- | --- | --- |
| GET | `/api/health/` | публичный | Проверка доступности сервиса и БД |

## Аутентификация (`/api/auth/`)

| Метод | Путь | Доступ | Описание |
| --- | --- | --- | --- |
| POST | `/api/auth/login/` | публичный | Вход: `email`, `password` → `access`, `refresh`, `user` |
| POST | `/api/auth/refresh/` | публичный | Обновление: `refresh` → `access` (и новый `refresh`) |
| POST | `/api/auth/logout/` | авторизованный | Выход: `refresh` заносится в чёрный список |
| GET | `/api/auth/me/` | авторизованный | Текущий пользователь |
| PATCH | `/api/auth/me/` | авторизованный | Изменение своего профиля (`first_name`, `last_name`, `middle_name`, `phone`, `language`) |
| POST | `/api/auth/change-password/` | авторизованный | Смена пароля: `old_password`, `new_password`, `new_password_confirm` |

### Пример входа

```http
POST /api/auth/login/
Content-Type: application/json

{ "email": "admin@example.com", "password": "admin12345" }
```

```json
{
  "access": "<jwt>",
  "refresh": "<jwt>",
  "user": {
    "id": 1,
    "email": "admin@example.com",
    "full_name": "Administrator System",
    "role": "admin",
    "role_display": "Administrator",
    "language": "",
    "is_active": true,
    "is_superuser": true
  }
}
```

## Пользователи (`/api/users/`)

Требуется право `core.users.view` для чтения и `core.users.manage` для
изменения. Иначе возвращается `403`.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/users/` | Список пользователей (с пагинацией, поиском, фильтрами) |
| POST | `/api/users/` | Создание пользователя |
| GET | `/api/users/{id}/` | Карточка пользователя |
| PATCH | `/api/users/{id}/` | Изменение пользователя |
| DELETE | `/api/users/{id}/` | Деактивация (`?permanent=true` — полное удаление) |
| POST | `/api/users/{id}/activate/` | Активировать пользователя |
| POST | `/api/users/{id}/deactivate/` | Деактивировать пользователя |

### Параметры списка

| Параметр | Описание |
| --- | --- |
| `page` | Номер страницы |
| `page_size` | Размер страницы (по умолчанию 20, максимум 100) |
| `search` | Поиск по `email`, имени, фамилии, отчеству, телефону |
| `roles` | Фильтр по коду роли (например `cashier`) |
| `is_active` | Фильтр по активности (`true` / `false`) |
| `ordering` | Сортировка (`email`, `last_name`, `first_name`, `role`, `date_joined`) |

### Создание пользователя

```http
POST /api/users/
Content-Type: application/json

{
  "email": "cashier@example.com",
  "password": "strong-pass-123",
  "password_confirm": "strong-pass-123",
  "first_name": "Anna",
  "last_name": "Sidorova",
  "roles": ["cashier"],
  "branch_access": [
    { "branch": 3, "include_descendants": true }
  ],
  "phone": "+7-900-000-00-00",
  "language": "",
  "is_active": true
}
```

Поля `email`, `password`, `password_confirm`, `first_name`, `last_name`
обязательны. Роли передаются списком кодов. Пароль проверяется встроенными
валидаторами Django.

В ответе пользователя возвращаются коды ролей (`roles`), их названия
(`roles_display`), объединённый список прав (`permissions`) и доступные
отделения (`branch_access`).

### Доступные отделения

Поле `branch_access` задаёт список доступных пользователю отделений — это
список объектов `{ "branch": <id>, "include_descendants": <bool> }`. Настройка
доступна по праву `core.users.manage`.

- **Deny-by-default:** если список пуст или не передан, пользователь не видит ни
  одного отделения. Суперпользователь видит все отделения всегда.
- `include_descendants: true` добавляет к отделению все его дочерние отделения
  (рекурсивно).
- При обновлении (`PATCH`) переданный список **заменяет** текущий; если поле не
  передано, доступ не меняется.
- Область доступа влияет на видимость отделений, касс и смен, а также на выбор
  рабочего места. Деактивация отделения доступ не снимает: ранее выполненную
  работу по нему видно, но открыть там смену нельзя.

### Формат ответа списка

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/users/?page=2",
  "previous": null,
  "results": [ { "id": 1, "email": "..." } ]
}
```

## Роли (`/api/roles/`)

Требуется право `core.roles.view` для чтения и `core.roles.manage` для
изменения. Системные роли (`is_system = true`) нельзя удалить.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/roles/` | Список ролей (поиск по `name`, `code`) |
| POST | `/api/roles/` | Создание роли: `name`, `description?`, `permissions[]` |
| GET | `/api/roles/{id}/` | Карточка роли |
| PATCH | `/api/roles/{id}/` | Изменение роли |
| DELETE | `/api/roles/{id}/` | Удаление роли (кроме системных) |

Права передаются списком кодов из каталога. Неизвестный код отклоняется (`400`).

## Каталог прав (`/api/permissions/`)

| Метод | Путь | Доступ | Описание |
| --- | --- | --- | --- |
| GET | `/api/permissions/` | `core.roles.view` | Каталог прав: `[{ "code", "name" }]` |

Каталог **собирается из модулей**: каждый модуль объявляет свои коды
(например, `operations.*`), а эндпоинт отдаёт объединение (см.
`docs/adr/0012-permission-catalog-aggregation.md`). Новые коды назначаются ролям
через интерфейс ролей.

## Отделения (`/api/branches/`)

Требуется право `core.structure.view` для чтения и `core.structure.manage` для
изменения. Отделения образуют дерево с единственным головным офисом.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/branches/` | Список **доступных** отделений (поиск по `name`, `code`, `address`) |
| POST | `/api/branches/` | Создание: `name`, `code?`, `parent?`, `is_head_office`, ... |
| GET | `/api/branches/{id}/` | Карточка отделения |
| PATCH | `/api/branches/{id}/` | Изменение отделения |
| DELETE | `/api/branches/{id}/` | Удаление (запрещено при дочерних отделениях или кассах) |
| GET | `/api/branches/selectable/` | Доступные активные отделения с активной кассой (для выбора) |
| GET | `/api/branches/structure-options/` | **Все** отделения для выбора вышестоящего (право `core.structure.manage`) |
| GET | `/api/branches/catalog/` | **Все** отделения для назначения доступа (право `core.users.manage`) |

Идентификатор `id` генерируется автоматически. Поле `code` необязательно:
если банк ведёт внутренние идентификаторы, его можно указать, иначе `code`
остаётся `null`. Заданный код уникален.

Головной офис создаётся без родителя; любое другое отделение требует `parent`.
Ветка не может быть своим предком (`400`).

### Выбор отделения (`/api/branches/selectable/`)

Доступно любому авторизованному пользователю, в том числе кассиру (без права
`core.structure.view`). Возвращает пагинированный список
`[{ "id", "name", "code" }]` **доступных** активных отделений, у которых есть
хотя бы одна активная касса. Поддерживает `search` по названию и коду.

### Каталог отделений (`/api/branches/catalog/`)

Требуется право `core.users.manage`. Возвращает **все** отделения (полные
объекты), независимо от личной области доступа вызывающего, — это нужно, чтобы
администратор мог назначать доступ, даже если сам видит не все отделения.

### Отделения для редактора структуры (`/api/branches/structure-options/`)

Требуется право `core.structure.manage`. Возвращает **все** отделения в виде
`[{ "id", "name", "code" }]`, независимо от личной области доступа вызывающего:
право редактировать структуру позволяет выбрать любое вышестоящее отделение,
даже недоступное по `BranchAccess`. Эндпоинт используют формы отделения и кассы.
Списки же (`/api/branches/`, `/api/cash-desks/`) остаются ограничены областью
доступа, а создание, изменение и удаление требуют `core.structure.manage`.

## Кассы (`/api/cash-desks/`)

Требуется право `core.structure.view` для чтения и `core.structure.manage` для
изменения.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/cash-desks/` | Список касс **доступных** отделений (фильтр `branch`, `is_active`; поиск по коду, имени, MAC) |
| POST | `/api/cash-desks/` | Создание: `branch`, `name`, `code?`, `mac_address?`, `hostname?` |
| GET | `/api/cash-desks/{id}/` | Карточка кассы |
| PATCH | `/api/cash-desks/{id}/` | Изменение кассы |
| DELETE | `/api/cash-desks/{id}/` | Удаление (запрещено при наличии смен) |
| GET | `/api/cash-desks/selectable/` | Активные кассы для выбора, с фильтром `branch` |

Идентификатор `id` генерируется автоматически. Поле `code` необязательно и
уникально, когда задано (см. отделения). MAC-адрес хранится в формате
`AA:BB:CC:DD:EE:FF` (приводится к верхнему регистру) и уникален.

### Выбор кассы (`/api/cash-desks/selectable/`)

Доступно любому авторизованному пользователю, в том числе кассиру. Возвращает
пагинированный список `[{ "id", "name", "code", "branch" }]` **доступных**
активных касс активных отделений. Параметр `branch` сужает выбор до одного
отделения, `search` ищет по названию и коду.

### Валюты кассы (`/api/cash-desks/{id}/currencies/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/cash-desks/{id}/currencies/` | `core.structure.view` | Действующие валюты кассы |
| PUT | `/api/cash-desks/{id}/currencies/` | `core.currencies.config.manage[.branch]` | Задать свою настройку кассы |

Действующие валюты кассы вычисляются **динамически** (см.
`docs/adr/0014-cash-desk-configuration-templates.md`): если у кассы есть своя
настройка — берётся она; иначе ближайший определённый шаблон по пути «отделение
→ … → банк» (правило перекрытия); если шаблонов нет — **не разрешена ни одна
валюта** (deny-by-default). Поле `source` сообщает источник (`own`, `branch`,
`bank`, `none`), `template_branch_id` — отделение применённого шаблона.

```http
PUT /api/cash-desks/7/currencies/
Content-Type: application/json

{ "currencies": ["USD", "BYN"] }
```

```json
{
  "cash_desk": 7,
  "configured": true,
  "source": "own",
  "template_branch_id": null,
  "currencies": [
    { "code": "BYN", "name": "Белорусский рубль", "symbol": "Br", "minor_units": 2 },
    { "code": "USD", "name": "Доллар США", "symbol": "$", "minor_units": 2 }
  ]
}
```

Неизвестный код валюты отклоняется (`400`). Пустой список **снимает** свою
настройку (касса возвращается к шаблону). Наличие валюты на кассе проверяется при
проведении операции (см. «Кассовые операции»). Право
`core.currencies.config.manage.branch` ограничивает настройку доступными
отделениями и не даёт менять шаблон банка; `core.currencies.config.manage`
снимает все ограничения.

### Шаблоны валют (`/api/currency-templates/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/currency-templates/` | `core.structure.view` | Определённые шаблоны (банк и доступные отделения) |
| GET | `/api/currency-templates/bank/` | `core.structure.view` | Шаблон банка |
| PUT | `/api/currency-templates/bank/` | `core.currencies.config.manage` | Задать шаблон банка |
| DELETE | `/api/currency-templates/bank/` | `core.currencies.config.manage` | Удалить шаблон банка |
| GET | `/api/currency-templates/branches/{id}/` | `core.structure.view` | Шаблон отделения |
| PUT | `/api/currency-templates/branches/{id}/` | `core.currencies.config.manage[.branch]` | Задать шаблон отделения |
| DELETE | `/api/currency-templates/branches/{id}/` | `core.currencies.config.manage[.branch]` | Удалить шаблон отделения |

Тело PUT — `{ "currencies": [...] }`. Пустой список — определённый **пустой
шаблон**, запрещающий все валюты. Отдельный GET возвращает `defined: false`,
когда шаблон не задан, и `defined: true` с содержимым, когда задан.

## Справочники (`/api/references/`)

Общесистемные справочные данные модуля `references` (см.
`docs/adr/0017-references-module.md`). Валюты и типы курсов живут в схеме
`references`; другие модули ссылаются на них по коду.

### Валюты (`/api/references/currencies/`)

Справочник валют ISO 4217. Требуется право `references.view` для чтения и
`references.manage` для изменения.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/references/currencies/` | Список валют (фильтр `is_active`, поиск по `code`, `numeric_code`, `name`) |
| POST | `/api/references/currencies/` | Добавить валюту: `code`, `name`, `numeric_code?`, `symbol?`, `minor_units?`, `is_active?` |
| GET | `/api/references/currencies/{code}/` | Карточка валюты |
| PATCH | `/api/references/currencies/{code}/` | Изменение валюты |
| DELETE | `/api/references/currencies/{code}/` | Удаление |

Код приводится к верхнему регистру и уникален. Справочник наполняется полным
списком действующих кодов ISO 4217 командой `seed_iso_currencies`. Название —
базовое (русское), английское хранится в таблице переводов и отдаётся на языке
запроса (ADR 0016).

### Типы курсов (`/api/references/rate-types/`)

Банковские типы курсов. Требуется право `references.view` для чтения и
`references.manage` для изменения.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/references/rate-types/` | Список типов (фильтры `is_active`, `principle`) |
| POST | `/api/references/rate-types/` | Добавить тип: `code`, `name`, `principle`, `validity?`, `daily_required?`, `is_active?`, `order?` |
| GET | `/api/references/rate-types/{id}/` | Карточка типа |
| PATCH | `/api/references/rate-types/{id}/` | Изменение типа |
| DELETE | `/api/references/rate-types/{id}/` | Удаление (системный тип удалить нельзя) |

`principle` — один из фиксированных принципов `official` (курс Нацбанка), `buy`,
`sell`, `conversion`; на него опирается логика операций. Системные типы
поставляются и не удаляются; банк может добавлять свои типы с любым принципом.

Системные типы: `official`, `buy`, `sell`, `conversion`, а также две стороны
прямой конверсии — `conversion_buy` и `conversion_sell` (см. «Прямые курсы
конверсии»). Последние два имеют принцип `conversion`.

`validity` — как хранится курс: `calendar_day` («На календарный день», один
действующий курс на дату и область) или `since_set` («С момента установки»,
действует с указанных даты и времени). `daily_required` — требуется ли курс на
дату выполнения операции. По умолчанию для принципа `official`:
`calendar_day` + `daily_required = true`; для остальных: `since_set` +
`daily_required = false`. После появления курсов этого типа `validity` изменить
нельзя (будет `400`); `daily_required` менять можно.

## Курсы валют (`/api/currency-rates/`)

Курсы валют банка, отделений и касс. Чтение — `core.currency_rates.view`.
Установка — одно из прав: `core.currency_rates.manage` (банк),
`core.currency_rates.manage.branch` (доступные отделения и их кассы),
`core.currency_rates.manage.cash_desk` (касса открытой смены),
`core.currency_rates.manage.official` (курс Нацбанка, только банк).

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/currency-rates/` | **Журнал**: все курсы, включая заменённые версии |
| POST | `/api/currency-rates/` | Установить один курс |
| GET | `/api/currency-rates/{id}/` | Карточка записи журнала |
| POST | `/api/currency-rates/bulk/` | Установить несколько курсов одного типа и области |
| POST | `/api/currency-rates/conversion-bulk/` | Установить прямые пары конверсии (покупка и продажа) |
| GET | `/api/currency-rates/current/` | Действующие курсы на момент просмотра (или `?at=`) |
| GET | `/api/currency-rates/resolve/` | Курс, который применила бы операция |

### Поля курса

- `currency`, `base_currency` — коды из `/api/references/currencies/`; для
  неконверсионных курсов и конверсии через базовую валюту `base_currency` должна
  совпадать с национальной валютой банка; для прямых кросс-курсов допускается
  любая пара; валюта котировки должна отличаться от валюты;
- `rate_type` — код типа курса из `/api/references/rate-types/`;
- `units` — количество единиц валюты, за которое задан курс (по умолчанию `1`,
  например `100` для курса RUB за 100 единиц);
- `value` — значение курса больше нуля (за `units` единиц);
- `branch`, `cash_desk` — область: оба пусты — банк, задан `branch` — отделение,
  задан `cash_desk` — касса; одновременно задавать нельзя;
- `effective_date` — дата для `calendar_day`;
- `effective_from` — дата и время для `since_set`;
- `scope` — вычисляемое `bank` / `branch` / `cash_desk`;
- `is_current`, `superseded_at` — признак действующей версии;
- `created_by`, `created_by_email`, `created_at` — кто и когда установил;
- `branch_name`, `cash_desk_name` — названия области для журнала.

Курс Нацбанка (`principle = official`) задаётся только для банка. Для
`calendar_day` в записи хранится `effective_date`, а `effective_from`
нормализуется на начало локального дня. Для `since_set` используется только
`effective_from`.

### Версии и замена

Для `calendar_day` действует ровно один курс на дату и область. Одиночный
`POST` на занятую дату возвращает `400`. `POST /bulk/` работает как upsert:
повторная установка создаёт новую версию, прежняя помечается `superseded_at` и
остаётся в журнале. Для `since_set` дубликат времени (`effective_from`) с той же
областью возвращает `400`.

### Прямые курсы конверсии

При `conversion_mode = direct` пара задаётся напрямую: `currency = EUR`,
`base_currency = USD` (то есть `1 EUR = X USD`). Пара хранится двумя
независимыми котировками — системные типы `conversion_buy` («Покупка
(конверсия)») и `conversion_sell` («Продажа (конверсия)»), по одной записи на
каждую сторону. Обе котировки разрешаются через `/api/currency-rates/resolve/`
с `target_currency = USD` и участвуют в журнале и текущих курсах как обычные
записи с валютой котировки USD. При `conversion_mode = via_base` такие пары
отклоняются (`400`).

`POST /api/currency-rates/conversion-bulk/` принимает `branch?`, `cash_desk?`,
`effective_date?`/`effective_from?` и `pairs: [{ currency, base_currency,
units?, buy, sell }]`. Запрос атомарен: для каждой пары создаются две записи
(`conversion_buy` со значением `buy` и `conversion_sell` со значением `sell`).
Оба системных типа имеют `validity = since_set`, поэтому `effective_from`
обязателен, а `effective_date` не принимается. Валюты пары должны различаться,
`buy` и `sell` — больше нуля, повтор пары в одном запросе — `400`. Установка
доступна тем же правам, что и `/bulk/`, и только при включённом прямом режиме
конверсии.

### Области и разрешение курса

Порядок разрешения для неофициальных курсов: касса → её отделение → родительские
отделения → банк. Признак `uses_individual_rates` у кассы отключает курсы
отделения и банка, у отделения — курсы банка и вышестоящих отделений. При этом
собственный курс кассы имеет приоритет, а курс родительского отделения
наследуется дочерними отделениями, пока более близкое отделение не задаст свой.
Курс Нацбанка всегда действует на уровне банка и не зависит от этих признаков.

Если у типа `daily_required = true`, разрешается только курс на дату операции
(для `calendar_day`) или установленный в эту дату (для `since_set`); при
`daily_required = false` берётся последнее значение на момент операции.

### Параметры журнала и текущих курсов

`currency`, `base_currency`, `rate_type`, `scope` (`bank` / `branch` /
`cash_desk`), `branch`, `cash_desk`, `effective_date_from`,
`effective_date_to`, `effective_from_from`, `effective_from_to`, `created_from`,
`created_to`, `created_by`, `is_current`, `search`, `page`. Журнал
дополнительно поддерживает `ordering`.
Для `current` дополнительно `at` (ISO 8601) — момент, на который строится
список.

Видимость: банковские курсы доступны всем с правом просмотра, курсы отделений и
касс — только в пределах доступных пользователю отделений.

### Установка нескольких курсов

`POST /api/currency-rates/bulk/` принимает `rate_type`, `base_currency?`,
`branch?`, `cash_desk?`, `effective_date?`/`effective_from?` и
`items: [{ currency, units?, value }]`. Операция атомарна: при ошибке не
сохраняется ни одна строка.

### Разрешение одного курса

`GET /api/currency-rates/resolve/?currency=EUR&target_currency=USD&rate_type=conversion&cash_desk=1&at=...`
возвращает действующую запись либо `404` с `code = rate_not_set`. Без
`cash_desk` разрешается только курс банка. Для обычных курсов и конверсии через
базовую валюту используется национальная валюта банка
(`BankSettings.base_currency`). В режиме `conversion_mode = direct` параметр
`target_currency` задаёт валюту котировки прямой пары. `value` в ответе задан за
`units` единиц; `value_per_unit` в контракте нормализует его к одной единице.
Контракт `core.cash_desk_config` использует тот же алгоритм.

## Кассовые смены (`/api/shifts/`)

| Метод | Путь | Доступ | Описание |
| --- | --- | --- | --- |
| GET | `/api/shifts/` | `core.shifts.view` | Список смен (см. параметры ниже) |
| POST | `/api/shifts/` | `core.shifts.open` | Открыть смену: `cash_desk` |
| GET | `/api/shifts/{id}/` | `core.shifts.view` | Карточка смены |
| GET | `/api/shifts/current/` | `core.shifts.view` | Открытая смена текущего пользователя или `null` |
| POST | `/api/shifts/{id}/close/` | `core.shifts.close` | Закрыть свою смену |
| POST | `/api/shifts/{id}/force-close/` | `core.shifts.manage` | Закрыть любую смену |

Смена привязывается к кассе при открытии. Одновременно допускается не более
одной открытой смены на кассира и на кассу (иначе `400`).

### Параметры списка

| Параметр | Описание |
| --- | --- |
| `status` | `open` или `closed` |
| `branch` | Отделение (через кассу смены) |
| `cash_desk` | Касса |
| `cashier` | Кассир |
| `opened_from` | Начало периода открытия, ISO 8601 |
| `opened_to` | Конец периода открытия, ISO 8601 |
| `ordering` | Сортировка (`opened_at`, `closed_at`) |

### Область видимости

Видимость смен — пересечение двух правил:

- **Область отделений:** видны только смены, чья касса принадлежит доступному
  пользователю отделению (см. «Доступные отделения»). Неактивные отделения
  остаются видимыми.
- **Область роли:** кассир, который открывает и закрывает смены, но не управляет
  ими (`core.shifts.manage`), видит только свои смены; остальные пользователи
  видят все смены в своих отделениях.

Принудительное закрытие (`force-close`) доступно только в пределах доступных
отделений. Открыть смену можно только на кассе активного отделения и активной
кассы, к которым у пользователя есть доступ (иначе `400`).

## Кассовые операции (`/api/operations/`)

Движок кассовых операций. Требуется право `operations.view` для чтения,
`operations.create` для проведения, `operations.reverse` для сторнирования,
`operations.config.manage` для изменения настроек комплектации,
`operations.types.manage` для изменения настроек типов. Если у типа операции задан
`permission_code`, он проверяется дополнительно.

Коды `operations.*` назначаются ролям через интерфейс ролей (каталог прав
агрегируется из модулей, см. `docs/adr/0012-permission-catalog-aggregation.md`).

**Касса и смена операции не передаются в запросе.** Они определяются по открытой
смене кассира (см. «Кассовые смены»): операция проводится на кассе открытой
смены. Чтение ограничено доступными пользователю отделениями (доступными кассами).

### Типы операций (`/api/operations/types/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/types/` | `operations.view` | Каталог типов операций |
| GET | `/api/operations/types/{code}/` | `operations.view` | Тип операции со слотами сумм |
| PATCH | `/api/operations/types/{code}/` | `operations.types.manage` | Изменить настройки типа |
| GET | `/api/operations/types/{code}/history/` | `operations.view` | История изменений настроек |
| GET | `/api/operations/types/{code}/print-configs/` | `operations.view` | Печатные документы типа |
| PUT | `/api/operations/types/{code}/print-configs/` | `operations.types.manage` | Заменить печатные документы типа |
| GET | `/api/operations/print-templates/` | `operations.view` | Доступные типы документов и шаблоны |
| GET | `/api/operations/threshold-types/` | `operations.view` | Предопределённые способы задания порога |

Параметры списка: `kind`, `is_active`, `is_external`, `client_data_policy`
(фильтры), `search` (по `code`, `name`), `ordering` (`name`, `code`).

В ответе тип содержит массив `slots` (`code`, `name`, `required`,
`fixed_currency`, `order`, `multiple`, `currency_policy`, `amount_mode`,
`computation`, `stores_rate`, `threshold_basis`) — по нему строится форма
проведения. Поле `form` задаёт вид формы: `amount`, `multi_currency` или
`exchange`; `rate_principle` — направление курса обмена (`buy`, `sell`,
`conversion`).

Администратор может изменить только настройки: `client_data_policy`, `threshold_type`,
`threshold_value`, `threshold_currency`, `rate_type`, `is_active`. Код, название,
вид, форма, слоты и шаблон проводок остаются декларативными и не перезаписываются.

Для типа с видом `exchange` поле `rate_type` обязательно: это код банковского
типа курса из `/api/references/rate-types/`, принцип которого совпадает с
`rate_principle`. Без настроенного типа курса операция обмена не проводится.

Политика данных клиента:

| Значение | Смысл |
| --- | --- |
| `never` | данные клиента не запрашиваются; порог не задаётся |
| `always` | данные клиента запрашиваются всегда |
| `threshold` | данные запрашиваются при превышении порога; тип и значение порога обязательны |

Проверка выполняется при проведении и в предварительном просмотре. При `always`
обязательны оба поля — `client_name` и `client_document`. При `threshold`
сравнивается сумма слотов с `threshold_basis`: для обмена это «Принято от
клиента», для остальных операций — суммы всех слотов. Сравнение строгое (`>`),
иностранные суммы пересчитываются по курсу Национального банка (`official`).
Если курс или действующая базовая величина недоступны, операция отклоняется.

Способы задания порога (`threshold_type`) заданы в коде:

| Код | Параметры |
| --- | --- |
| `base_value` | `threshold_value` — количество базовых величин |
| `currency` | `threshold_value` — сумма, `threshold_currency` — код валюты |

Изменения настроек фиксируются в истории с датой, временем и пользователем; история
ведётся и при изменении через Django admin. В элементе истории поле `changes`
содержит значения «до/после» по каждому изменённому полю.

Печатные документы типа операции:

```http
PUT /api/operations/types/currency_purchase/print-configs/
Content-Type: application/json

{
  "configs": [
    {
      "document_type": "cash_receipt",
      "template": "cash_receipt_currency_purchase",
      "is_active": true
    }
  ]
}
```

Список заменяется целиком: отсутствующий тип документа больше не печатается.
Шаблон должен принадлежать выбранному типу документа (проверяется по контракту
`printing`). Ответ — массив `{document_type, document_type_name, template,
template_name, is_active}`. `print_configs` также входит в ответ типа операции.
Доступные типы документов и шаблоны с переменными возвращает
`GET /api/operations/print-templates/`.

### Остатки наличных (`/api/operations/balances/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/balances/` | `operations.view` | Остатки наличных по кассам и валютам |
| GET | `/api/operations/balances/{id}/` | `operations.view` | Один остаток |

Остаток ведётся по паре (касса, валюта). Параметры: `cash_desk`, `currency`.
Список ограничен доступными кассами. Остаток не может быть отрицательным: расход
сверх наличия отклоняется при проведении.

### Журнал операций (`/api/operations/operations/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/operations/` | `operations.view` | Журнал операций (см. параметры) |
| POST | `/api/operations/operations/` | `operations.create` | Провести операцию |
| POST | `/api/operations/operations/preview/` | `operations.create` | Проверить и подготовить операцию без проведения |
| GET | `/api/operations/operations/{id}/` | `operations.view` | Карточка операции (строки и проводки) |
| POST | `/api/operations/operations/{id}/reverse/` | `operations.reverse` | Сторнировать операцию |

В строке журнала и карточке есть `has_print_documents`: были ли при проведении
созданы печатные документы. Ответ проведения дополнительно содержит
`print_documents` — метаданные созданных документов (`id`, тип, шаблон, номер,
имя файла). Если включённые шаблоны не сформировали ни одного документа,
массив пуст.

Параметры списка: `cash_desk`, `shift`, `cashier`, `operation_type` (код),
`direction` (вид: `income` / `expense` / `exchange` / `internal`), `status`,
`posted_from` / `posted_to` (ISO 8601), `ordering` (`posted_at`, `number`, `id`).

#### Проведение операции

```http
POST /api/operations/operations/
Content-Type: application/json

{
  "operation_type": "cash_receipt",
  "lines": [
    {
      "slot": "amount",
      "currency": "USD",
      "amount": "500.00",
      "rate": null,
      "rate_is_individual": false
    }
  ],
  "client_name": "Иванов И. И.",
  "client_document": "AB 1234567",
  "comment": "",
  "idempotency_key": "<уникальный ключ операции>"
}
```

Правила:

- тип операции должен быть активным, а его `permission_code` (если задан) —
  выдан пользователю, иначе `403`;
- операция должна быть доступна на кассе (комплектация кассы) — иначе `400`;
- валюты строк должны быть доступны на кассе — иначе `400`;
- суммы проверяются по слотам типа (обязательные, известные, фиксированные валюты,
  положительные суммы) — иначе `400`;
- слот с `multiple = true` принимает несколько строк — по одной на валюту;
- слот с `currency_policy = base` принимает только национальную валюту, с
  `foreign` — только иностранную;
- для обмена суммы и курсы проверяются движком: курс берётся из настроенного
  `rate_type`, вычисляемая строка пересчитывается на сервере; индивидуальный курс
  (`rate_is_individual = true`) должен быть больше нуля;
- для обмена поле `basis_slot` называет сторону, сумму которой ввёл кассир
  (`received` — получено от клиента или `issued` — выдано клиенту). Пустое
  значение сохраняет объявленную входную сторону (`received`). Направление курса
  не зависит от выбора: курс берётся по `rate_principle`, а вторая сторона
  пересчитывается обратной операцией (`multiply` ↔ `divide`); сумма известной
  стороны должна быть больше нуля, переданная сумма вычисляемой стороны
  игнорируется;
- данные клиента проверяются по политике типа (см. «Типы операций»); при
  необходимости оба поля обязательны — иначе `400` с ошибками полей;
- расход не может превысить остаток наличных в кассе — иначе `400` (и ничего не
  записывается);
- повтор запроса с тем же `idempotency_key` на той же кассе возвращает уже
  проведённую операцию (`201`), дубля не создаётся;
- без открытой смены у кассира — `400`.

#### Предварительный просмотр

`POST /api/operations/operations/preview/` принимает те же данные, что и
проведение (включая `basis_slot`), применяет те же правила, но ничего не
записывает. Ответ содержит нормализованные строки (`lines`) и результат
проверки данных клиента:

```json
{
  "operation_type": "currency_purchase",
  "operation_type_name": "Покупка валюты у клиента",
  "lines": [
    { "slot": "received", "currency": "USD", "amount": "100.00", "rate": "3.25000000", "rate_type": "buy", "rate_is_individual": false },
    { "slot": "issued", "currency": "BYN", "amount": "325.00", "rate": null, "rate_type": "", "rate_is_individual": false }
  ],
  "client_data": {
    "policy": "always",
    "required": true,
    "reason": "always",
    "amount": null,
    "threshold": null,
    "currency": ""
  }
}
```

`reason` принимает значения `never`, `always`, `threshold` (порог превышен) и
`below_threshold`. При превышении порога в `amount`, `threshold` и `currency`
возвращаются сумма, порог и валюта сравнения.

#### Сторнирование

Создаёт обратную операцию (со ссылкой на исходную) и помечает исходную как
`reversed`. Повторное сторно и сторно-сторно запрещены (`400`). Расход сверх
остатка при сторно также отклоняется.

### Рабочее место кассира (`/api/operations/workplace/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/workplace/` | `operations.view` | Контекст экрана кассира |

Возвращает всё, что нужно экрану: открытую смену и кассу, остатки наличных,
доступные на кассе операции (со слотами и метаданными формы), доступные валюты,
национальную валюту, режим конверсии и действующую базовую величину. Если смены
нет — пустой контекст (`shift_id: null`).

Действующие курсы упорядочены по типу курса (в порядке типов справочника), затем
по валюте и валюте курса. `rate_type_display` — название типа курса для заголовка
группы на экране кассира.

```json
{
  "shift_id": 11,
  "cash_desk_id": 7,
  "base_currency": "BYN",
  "conversion_mode": "via_base",
  "base_value": "40.00",
  "base_value_date": "2026-01-01",
  "currencies": [ { "code": "USD", "name": "Доллар США", "symbol": "$", "minor_units": 2 } ],
  "rates": [
    { "currency": "USD", "base_currency": "BYN", "rate_type": "buy", "rate_type_display": "Покупка", "units": 1, "value": "3.250000", "value_per_unit": "3.250000", "effective_from": "..." }
  ],
  "balances": [
    { "cash_desk_id": 7, "currency": "USD", "amount": "500.00", "updated_at": "..." }
  ],
  "operations": [
    {
      "code": "currency_purchase",
      "name": "Покупка валюты у клиента",
      "kind": "exchange",
      "form": "exchange",
      "client_data_policy": "always",
      "requires_client": true,
      "threshold_type": "",
      "threshold_value": null,
      "threshold_currency": "",
      "rate_principle": "buy",
      "rate_type": "buy",
      "rate_type_display": "Курс покупки",
      "slots": [
        { "code": "received", "name": "Принято от клиента", "required": true, "fixed_currency": "", "order": 0, "multiple": false, "currency_policy": "foreign", "amount_mode": "input", "computation": "", "stores_rate": true, "threshold_basis": true },
        { "code": "issued", "name": "Выдано клиенту", "required": true, "fixed_currency": "", "order": 1, "multiple": false, "currency_policy": "base", "amount_mode": "computed", "computation": "multiply", "stores_rate": false, "threshold_basis": false }
      ]
    }
  ]
}
```

### Комплектация кассы (`/api/operations/cash-desks/{cash_desk}/operations/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/cash-desks/{cash_desk}/operations/` | `operations.view` | Действующие операции кассы |
| PUT | `/api/operations/cash-desks/{cash_desk}/operations/` | `operations.config.manage[.branch]` | Задать свою настройку кассы |

Действующие операции кассы вычисляются **динамически** (см.
`docs/adr/0014-cash-desk-configuration-templates.md`): своя настройка кассы →
ближайший определённый шаблон по пути «отделение → … → банк» → при отсутствии
шаблонов **операции запрещены** (deny-by-default). Поле `source` — источник
(`own`, `branch`, `bank`, `none`), `template_branch_id` — отделение шаблона.

```http
PUT /api/operations/cash-desks/7/operations/
Content-Type: application/json

{ "operations": ["cash_receipt", "cash_handover"] }
```

```json
{
  "cash_desk_id": 7,
  "configured": false,
  "source": "bank",
  "template_branch_id": null,
  "operations": [
    { "code": "cash_receipt", "name": "Приход наличных от клиента", "kind": "income" }
  ]
}
```

Неизвестный код операции отклоняется (`400`). Пустой список **снимает** свою
настройку (касса возвращается к шаблону). Право
`operations.config.manage.branch` ограничивает настройку доступными отделениями и
не даёт менять шаблон банка; `operations.config.manage` снимает ограничения.

### Шаблоны операций (`/api/operations/operation-templates/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/operation-templates/` | `operations.view` | Определённые шаблоны (банк и доступные отделения) |
| GET | `/api/operations/operation-templates/bank/` | `operations.view` | Шаблон банка |
| PUT | `/api/operations/operation-templates/bank/` | `operations.config.manage` | Задать шаблон банка |
| DELETE | `/api/operations/operation-templates/bank/` | `operations.config.manage` | Удалить шаблон банка |
| GET | `/api/operations/operation-templates/branches/{id}/` | `operations.view` | Шаблон отделения |
| PUT | `/api/operations/operation-templates/branches/{id}/` | `operations.config.manage[.branch]` | Задать шаблон отделения |
| DELETE | `/api/operations/operation-templates/branches/{id}/` | `operations.config.manage[.branch]` | Удалить шаблон отделения |

Тело PUT — `{ "operations": [...] }`. Пустой список — определённый **пустой
шаблон**, запрещающий все операции. Отдельный GET возвращает `defined: false`,
когда шаблон не задан.

## Печатные документы (`/api/printing/`)

Модуль печатных документов. Требуемые права: `printing.templates.view` —
просмотр и скачивание шаблонов, `printing.templates.manage` — загрузка шаблонов,
`printing.print` — просмотр и скачивание документов операций. Доступ к
документам операции дополнительно ограничен доступными пользователю кассами.

### Шаблоны (`/api/printing/templates/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/printing/templates/` | `printing.templates.view` | Объявленные шаблоны печатных форм |
| GET | `/api/printing/templates/{code}/` | `printing.templates.view` | Один шаблон |
| GET | `/api/printing/templates/{code}/file/` | `printing.templates.view` | Скачать шаблон `.docx` |
| POST | `/api/printing/templates/{code}/file/` | `printing.templates.manage` | Загрузить шаблон `.docx` |

Загрузка — `multipart/form-data`, поле `file`. Принимается только документ Word
(`.docx`) размером до 10 МБ. Ответ содержит метаданные шаблона. Поле `variables`
перечисляет доступные переменные подстановки (`code`, `description`, `example`),
`has_file` показывает, загружен ли файл, `last_error` — последнюю ошибку
рендеринга. Параметры списка: `document_type`, `is_active`, `search`, `ordering`.

### Типы документов (`/api/printing/document-types/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/printing/document-types/` | `printing.templates.view` | Типы печатных документов |

### Документы операций (`/api/printing/operations/{id}/documents/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/printing/operations/{id}/documents/` | `printing.print` | Документы, созданные для операции |
| GET | `/api/printing/documents/{id}/file/` | `printing.print` | Скачать отрендеренный документ |

Документы операции возвращаются в порядке создания. Повторная печать
воспроизводит сохранённый при проведении `.docx` и не зависит от последующих
изменений шаблона. Документ недоступной кассы не возвращается (`404` для файла,
пустой список для операции).

## Коды ошибок

| Код | Значение |
| --- | --- |
| 400 | Ошибка валидации (тело содержит поля с сообщениями) |
| 401 | Требуется аутентификация / токен недействителен |
| 403 | Недостаточно прав |
| 404 | Объект не найден |
| 429 | Превышен лимит запросов (троттлинг входа) |
