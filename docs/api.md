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

Доступ только для администраторов (`IsAdminRole`). Для не-администраторов
возвращается `403`.

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
| `role` | Фильтр по роли |
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
  "role": "cashier",
  "phone": "+7-900-000-00-00",
  "is_active": true
}
```

Поля `email`, `password`, `password_confirm`, `first_name`, `last_name`, `role`
обязательны. Пароль проверяется встроенными валидаторами Django.

### Формат ответа списка

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/users/?page=2",
  "previous": null,
  "results": [ { "id": 1, "email": "..." } ]
}
```

## Коды ошибок

| Код | Значение |
| --- | --- |
| 400 | Ошибка валидации (тело содержит поля с сообщениями) |
| 401 | Требуется аутентификация / токен недействителен |
| 403 | Недостаточно прав |
| 404 | Объект не найден |
| 429 | Превышен лимит запросов (троттлинг входа) |
