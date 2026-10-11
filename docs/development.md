# Разработка

## Требования

- Docker Desktop (Windows, macOS или Linux).
- Git.

Локальные Python и Node.js не требуются — все инструменты доступны внутри
контейнеров.

## Первый запуск

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f backend
```

Проверка, что сервис жив:

```bash
curl http://localhost:8000/api/health/
# {"status": "ok", "database": true}
```

Адрес веб-интерфейса — http://localhost:5173. Начальный администратор создаётся
автоматически из `DJANGO_SUPERUSER_EMAIL` / `DJANGO_SUPERUSER_PASSWORD`.

## Ежедневный цикл

Vite dev-сервер и `runserver` отслеживают изменения и перезагружаются
автоматически, повторная сборка образа не нужна. Пересобирайте образ только при
изменении зависимостей (`requirements*.txt`, `package.json`):

```bash
docker compose up --build -d
```

## Backend

### Команды

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py shell
docker compose exec backend pytest
docker compose exec backend pytest modules/core/backend/tests/test_api.py -v
docker compose exec backend ruff check .
docker compose exec backend black .
```

### Добавление модуля

Модуль — вертикальный срез `modules/<name>/` (backend + frontend + contracts) с
манифестом `module.yaml`. Правила, контракты и полный порядок действий — в
`docs/modules.md` (раздел «Как добавить модуль»); шаблон — `modules/_template/`.

Кратко:

1. Создайте каталог `modules/<name>/backend/` — Django-приложение; в `AppConfig`
   задайте `name = "modules.<name>.backend"` и явный `label`.
2. Зарегистрируйте приложение в `INSTALLED_APPS` и подключите URL в
   `config/urls.py`.
3. Опишите контракт в `modules/<name>/contracts/` и зарегистрируйте его реализацию
   в реестре (`modules.common.contracts.registry`).
4. Создайте и примените миграции, напишите тесты.

## Frontend

### Команды

```bash
docker compose exec frontend npm run build     # проверка типов + сборка
docker compose exec frontend npm run dev       # dev-сервер (уже запущен в compose)
```

### Добавление страницы

Страницы фич живут в модулях (`modules/<name>/frontend/`), общий SDK и каркас —
в хосте (`frontend/src/`). Полные правила — в `docs/modules.md`, раздел
«Frontend модуля».

1. Компонент страницы — `modules/<name>/frontend/pages/`.
2. Запросы к API модуля — в `modules/<name>/frontend/api/`; общие блоки — из
   `@app/*`.
3. Маршрут и пункт навигации — в манифесте `modules/<name>/frontend/index.tsx`.
4. Включите модуль в `frontend/src/registry/index.ts`.

## Работа с базами данных

### SQLite → PostgreSQL

```bash
docker compose down
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build -d
```

Данные SQLite и PostgreSQL хранятся в отдельных томах (`sqlite_data` и
`postgres_data`), поэтому переключение не удаляет существующие данные.

### Сброс базы данных SQLite

```bash
docker compose down -v
docker compose up -d
```

## Промышленная сборка

```bash
DJANGO_SECRET_KEY="<длинный-случайный-ключ>" docker compose -f docker-compose.prod.yml up --build -d
```

Стек: PostgreSQL, backend под gunicorn, frontend (собранный SPA) за nginx на
порту 8080.

## Частые проблемы

| Симптом | Решение |
| --- | --- |
| `entrypoint.sh: set: Illegal option -` | Файл получил CRLF. Сохраните с LF (см. `.gitattributes`, `.editorconfig`) |
| Менеджер паролей браузера мешает вводу на странице входа | Это поведение браузера на SPA-страницах, а не ошибка приложения. Отключите сохранение паролей для `localhost` в настройках браузера |
| Backend перезапускается при старте | Посмотрите `docker compose logs backend`: обычно ошибка настроек или БД |
| Порт занят | Измените публикуемый порт в `docker-compose.yml` или остановите конфликтующий процесс |
| Изменения в зависимостях не применяются | Пересоберите образы: `docker compose up --build -d` |
