# REST API

Базовый префикс: `/api/`. Формат данных — JSON. Интерактивная документация
(Swagger UI) доступна по адресу `/api/docs/`, схема OpenAPI — `/api/schema/`.

Аутентификация — JWT. Для защищённых методов передавайте заголовок:

```
Authorization: Bearer <access_token>
```

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
| PATCH | `/api/auth/me/` | авторизованный | Изменение своего профиля (`first_name`, `last_name`, `middle_name`, `phone`) |
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
| GET | `/api/cash-desks/{id}/currencies/` | `core.structure.view` | Доступные валюты кассы |
| PUT | `/api/cash-desks/{id}/currencies/` | `core.structure.manage` | Задать доступные валюты |

Набор валют кассы — **opt-in**: пока он не задан, кассе доступны все активные
валюты (`configured: false`); после настройки — только перечисленные.

```http
PUT /api/cash-desks/7/currencies/
Content-Type: application/json

{ "currencies": ["USD", "BYN"] }
```

```json
{
  "cash_desk": 7,
  "configured": true,
  "currencies": [
    { "code": "BYN", "name": "Белорусский рубль", "symbol": "Br", "minor_units": 2 },
    { "code": "USD", "name": "Доллар США", "symbol": "$", "minor_units": 2 }
  ]
}
```

Неизвестный код валюты отклоняется (`400`). Пустой список снимает настройку
(касса снова без ограничений). Наличие валюты на кассе проверяется при
проведении операции (см. «Кассовые операции»).

## Валюты (`/api/currencies/`)

Справочник валют банка. Требуется право `core.structure.view` для чтения и
`core.structure.manage` для изменения.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/currencies/` | Список валют (фильтр `is_active`, поиск по `code`, `name`) |
| POST | `/api/currencies/` | Добавить валюту: `code`, `name`, `symbol?`, `minor_units?` |
| GET | `/api/currencies/{code}/` | Карточка валюты |
| PATCH | `/api/currencies/{code}/` | Изменение валюты |
| DELETE | `/api/currencies/{code}/` | Удаление (запрещено, если валюта включена на кассе) |

Код валюты приводится к верхнему регистру и уникален. При поставке добавляются
`BYN`, `USD`, `EUR`, `RUB`.

## Курсы валют (`/api/currency-rates/`)

Курсы валют банка и отдельных касс. Требуется право `core.structure.view` для
чтения и `core.structure.manage` для изменения.

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/currency-rates/` | Список курсов (фильтры `currency`, `base_currency`, `rate_type`, `cash_desk`) |
| POST | `/api/currency-rates/` | Добавить курс |
| GET | `/api/currency-rates/{id}/` | Карточка курса |
| PATCH | `/api/currency-rates/{id}/` | Изменение курса |
| DELETE | `/api/currency-rates/{id}/` | Удаление курса |

Поля: `currency` и `base_currency` (коды из справочника валют), `rate_type`
(`buy` / `sell` / `central`), `value`, `effective_from` (ISO 8601), `cash_desk`
(необязательно; пусто — курс банка). Базовая валюта должна отличаться от валюты.

Курсы **действуют по времени**: применяется запись с наибольшим
`effective_from` не в будущем. Курс кассы **перекрывает** курс банка. Разрешение
курса доступно модулям через контракт `core.references`.

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
`operations.config.manage` для изменения настроек. Если у типа операции задан
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

Параметры списка: `kind`, `is_active`, `is_external`, `requires_client` (фильтры),
`search` (по `code`, `name`), `ordering` (`name`, `code`).

В ответе тип содержит массив `slots` (`code`, `name`, `required`,
`fixed_currency`, `order`) — по нему строится форма проведения.

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
| GET | `/api/operations/operations/{id}/` | `operations.view` | Карточка операции (строки и проводки) |
| POST | `/api/operations/operations/{id}/reverse/` | `operations.reverse` | Сторнировать операцию |

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
    { "slot": "amount", "currency": "USD", "amount": "500.00", "rate": null }
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
- суммы проверяются по слотам типа (обязательные, известные, фиксированные валюты) —
  иначе `400`;
- расход не может превысить остаток наличных в кассе — иначе `400` (и ничего не
  записывается);
- повтор запроса с тем же `idempotency_key` на той же кассе возвращает уже
  проведённую операцию (`201`), дубля не создаётся;
- без открытой смены у кассира — `400`.

#### Сторнирование

Создаёт обратную операцию (со ссылкой на исходную) и помечает исходную как
`reversed`. Повторное сторно и сторно-сторно запрещены (`400`). Расход сверх
остатка при сторно также отклоняется.

### Рабочее место кассира (`/api/operations/workplace/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/workplace/` | `operations.view` | Контекст экрана кассира |

Возвращает всё, что нужно экрану: открытую смену и кассу, остатки наличных,
доступные на кассе операции (со слотами) и доступные валюты. Если смены нет —
пустой контекст (`shift_id: null`).

```json
{
  "shift_id": 11,
  "cash_desk_id": 7,
  "currencies": [ { "code": "USD", "name": "Доллар США", "symbol": "$", "minor_units": 2 } ],
  "rates": [
    { "currency": "USD", "base_currency": "BYN", "rate_type": "buy", "value": "3.250000", "effective_from": "..." }
  ],
  "balances": [
    { "cash_desk_id": 7, "currency": "USD", "amount": "500.00", "updated_at": "..." }
  ],
  "operations": [
    {
      "code": "cash_receipt",
      "name": "Приход наличных",
      "kind": "income",
      "requires_client": true,
      "client_id_threshold": null,
      "slots": [ { "code": "amount", "name": "Сумма", "required": true, "fixed_currency": "", "order": 0 } ]
    }
  ]
}
```

### Комплектация кассы (`/api/operations/cash-desks/{cash_desk}/operations/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/cash-desks/{cash_desk}/operations/` | `operations.view` | Операции, доступные на кассе |
| PUT | `/api/operations/cash-desks/{cash_desk}/operations/` | `operations.config.manage` | Задать доступные операции |

Набор операций кассы — **opt-in**: пока он не задан, кассе доступны все активные
операции (`configured: false`); после настройки — только перечисленные.

```http
PUT /api/operations/cash-desks/7/operations/
Content-Type: application/json

{ "operations": ["cash_receipt", "cash_disbursement"] }
```

```json
{
  "cash_desk_id": 7,
  "configured": true,
  "operations": [
    { "code": "cash_receipt", "name": "Приход наличных", "kind": "income" }
  ]
}
```

Неизвестный код операции отклоняется (`400`). Пустой список снимает настройку
(касса снова без ограничений).

### Настройки (`/api/operations/settings/`)

| Метод | Путь | Право | Описание |
| --- | --- | --- | --- |
| GET | `/api/operations/settings/` | `operations.view` | Настройки операций |
| PATCH | `/api/operations/settings/` | `operations.config.manage` | Изменить настройки |

Единственный объект настроек банка: `base_currency`, `client_id_threshold`,
`require_client`.

## Коды ошибок

| Код | Значение |
| --- | --- |
| 400 | Ошибка валидации (тело содержит поля с сообщениями) |
| 401 | Требуется аутентификация / токен недействителен |
| 403 | Недостаточно прав |
| 404 | Объект не найден |
| 429 | Превышен лимит запросов (троттлинг входа) |
