# BankCashOps — Bank Cash Operation System

Система автоматизации учёта кассовых операций банка.

Проект построен по трёхуровневой архитектуре (Frontend → Backend → База данных),
развивается модульно и поставляется в контейнерах Docker.

## Стек

| Слой | Технологии |
| --- | --- |
| Backend | Python 3.12, Django 5, Django REST Framework, SimpleJWT |
| База данных | SQLite (разработка) → PostgreSQL (промышленная эксплуатация) |
| Frontend | React 18, TypeScript, Vite, Mantine |
| Инфраструктура | Docker, Docker Compose |

## Быстрый старт

Требуется установленный Docker Desktop. Локальные Python и Node.js не нужны —
всё собирается и запускается в контейнерах.

```bash
# 1. Создайте файл окружения (значения по умолчанию рабочие для разработки)
cp .env.example .env

# 2. Соберите и запустите стек
docker compose up --build -d

# 3. Посмотрите логи (необязательно)
docker compose logs -f backend
```

После запуска доступны:

| Что | Адрес |
| --- | --- |
| Веб-интерфейс | http://localhost:5173 |
| REST API | http://localhost:8000/api/ |
| Документация API (Swagger) | http://localhost:8000/api/docs/ |
| Админка Django | http://localhost:8000/admin/ |

При первом запуске автоматически создаётся администратор из переменных
окружения `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD`
(по умолчанию `admin@example.com` / `admin12345`). **Смените пароль после
первого входа.**

## Структура репозитория

```
BankCashOps/
├── backend/                  # Django-хост: настройки, URL, WSGI/ASGI
│   ├── config/               # Настройки, корневые URL, WSGI/ASGI
│   ├── Dockerfile            # Образ для разработки (контекст сборки — корень)
│   └── Dockerfile.prod       # Образ для эксплуатации (gunicorn)
├── frontend/                 # SPA на React + TypeScript + Vite
│   ├── src/
│   │   ├── api/              # HTTP-клиент и типы
│   │   ├── auth/             # Аутентификация и защита маршрутов
│   │   ├── components/       # Переиспользуемые компоненты
│   │   ├── pages/            # Хостовые страницы (панель, профиль, вход, 404)
│   │   └── registry/         # Реестр модулей (композиция маршрутов и навигации)
│   ├── Dockerfile            # Vite dev-сервер
│   └── Dockerfile.prod       # Сборка и раздача через nginx
├── modules/                  # Вертикальные модули (backend + frontend + contracts)
│   ├── common/               # Техническая библиотека (модели, права, пагинация, контракты)
│   ├── core/                 # Ядро: пользователи, аутентификация, роли
│   ├── _template/            # Заготовка нового модуля
│   └── README.md             # Соглашения по модулям
├── profiles/                 # Профили заказчиков (комплектация поставки)
├── docs/                     # Документация проекта
│   ├── adr/                  # Архитектурные решения
├── docker-compose.yml        # Стек разработки (SQLite)
├── docker-compose.postgres.yml   # Надстройка: PostgreSQL
├── docker-compose.prod.yml   # Промышленный стек
└── AGENTS.md                 # Правила для AI-агентов
```

## Полезные команды

Все команды выполняются из корня репозитория.

```bash
# Запуск и остановка
docker compose up -d
docker compose down

# Логи
docker compose logs -f backend
docker compose logs -f frontend

# Миграции
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate

# Тесты и линтер backend
docker compose exec backend pytest
docker compose exec backend ruff check .

# Проверка типов и сборка frontend
docker compose exec frontend npm run build
```

## Переключение на PostgreSQL

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build -d
```

## Промышленный запуск

```bash
DJANGO_SECRET_KEY="<длинный-случайный-ключ>" docker compose -f docker-compose.prod.yml up --build -d
```

Промышленный стек поднимает PostgreSQL, backend под gunicorn и frontend за
nginx. Интерфейс доступен на http://localhost:8080.

## Документация

- `docs/architecture.md` — архитектура и принципы модульности.
- `docs/modules.md` — модули, контракты, манифест и профили.
- `docs/adr/` — архитектурные решения (ADR).
- `docs/api.md` — описание REST API.
- `docs/development.md` — рабочие процессы разработки.
- `AGENTS.md` — правила для AI-агентов.

## Дорожная карта

Продукт развивается как модульный монолит со строгими границами
(`docs/adr/0001-modular-monolith.md`). Первый реализованный функциональный блок —
администрирование пользователей; он станет доменным модулем `core`. Следующие
модули (кассовые операции, кассы и смены, отчётность, аудит) добавляются как
вертикальные модули в `modules/` (`docs/modules.md`).
