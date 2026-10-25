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
изменении зависимостей (`requirements*.txt`, `package.json`). `pip` в образы не
устанавливается: зависимости попадают в образ на этапе сборки, поэтому ставить
пакеты в работающем контейнере не нужно (и не получится):

```bash
# --renew-anon-volumes пересоздаёт анонимный том node_modules фронтенда,
# иначе контейнер продолжит использовать зависимости из старого тома.
docker compose up --build -d --renew-anon-volumes
```

## Работа с Git и GitHub

Ветка `main` защищена: прямые изменения в неё запрещены, поэтому любая правка
идёт через отдельную ветку и pull request (PR). Имя ветки изменения начинается с
`feature/`, например `feature/postgres-in-development`. Проверки CI запускаются
на каждом PR, и влить изменения можно только после их успешного прохождения.

Цикл одной правки:

```bash
git switch -c feature/my-feature      # 1. новая ветка под задачу
# ... правки и коммиты ...
git push -u origin feature/my-feature # 2. отправить ветку на GitHub
```

3. Открыть PR: после push `git` печатает ссылку вида
   `https://github.com/<...>/pull/new/feature/my-feature` — откройте её и нажмите
   **Create pull request**.
4. Дождаться зелёных проверок CI (вкладка **Actions** или блок проверок внизу
   страницы PR).
5. Нажать **Merge pull request** → **Confirm merge**.

После слияния обновите локальный `main` и уберите рабочую ветку:

```bash
git switch main
git pull                          # подтянуть слитые изменения
git branch -d feature/my-feature # удалить локальную ветку
```

Если `main` ушёл вперёд, пока вы работали, и PR просит обновления, влейте
свежий `main` в свою ветку и отправьте её снова:

```bash
git switch feature/my-feature
git merge origin/main
git push
```

> При слиянии через *Squash and merge* локальные коммиты формально не попадают
> в `main`, поэтому `git branch -d` может отказаться удалять ветку — тогда
> используйте `git branch -D feature/my-feature`.

### Что проверяет CI

Workflow `.github/workflows/ci.yml` состоит из двух заданий:

| Задание | Проверки |
| --- | --- |
| Backend (ruff, pytest) | `ruff check`, компиляция каталогов переводов (`compilemessages`), поиск забытых миграций (`makemigrations --check`), `pytest` |
| Frontend (build) | `npm ci` и сборка SPA (`npm run build`) |

Те же проверки можно выполнить локально в контейнерах:

```bash
docker compose exec backend ruff check .
docker compose exec backend pytest
docker compose exec frontend npm run build
```

## Backend

### Команды

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py sync_operation_types
docker compose exec backend python manage.py sync_print_templates
docker compose exec backend python manage.py dispatch_outbox
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py shell
docker compose exec backend pytest
docker compose exec backend pytest modules/core/backend/tests/test_api.py -v
docker compose exec backend ruff check .
docker compose exec backend black .
```

`sync_operation_types` создаёт и обновляет типы кассовых операций, объявленные
установленными модулями (движок и базовый набор). `sync_print_templates` делает
то же для типов печатных документов и шаблонов печатных форм и устанавливает
образец `.docx`, если банк ещё не загрузил свой. Обе команды идемпотентны и уже
выполняются при старте backend (entrypoint, после миграций); вручную нужны после
изменения объявлений без перезапуска контейнера.

`dispatch_outbox` доставляет доменные события (outbox) подписчикам. С флагом
`--loop` работает непрерывно (воркер): `python manage.py dispatch_outbox --loop`.
Одиночный запуск годится для cron.

### Переводы (i18n)

Приложение мультиязычно. Слои и приоритеты языка — в
`docs/adr/0015-application-language-layers.md`, перевод справочных данных — в
`docs/adr/0016-translatable-reference-data.md`.

Каталоги переводов модуля живут в `modules/<name>/backend/locale/<lang>/LC_MESSAGES/`.
Исходные строки — английские, поэтому каталог нужен только для `ru`: при
отсутствии перевода отдаётся исходный английский текст. Строки собираются командой
`makemessages`, запущенной **в каталоге модуля** (тогда файлы попадают в его
`locale/`; сам каталог `locale/` должен существовать заранее — создайте его перед
первым запуском):

```bash
# Из корня репозитория; <module> — имя модуля (например core).
docker compose exec backend sh -c \
    "cd /app/modules/<module>/backend && python /app/manage.py makemessages -l ru"
```

Компиляция `.po` в `.mo` выполняется автоматически при старте backend
(`entrypoint.sh`); вручную — `python manage.py compilemessages`. Компилированные
`.mo` не коммитятся.

### Добавление модуля

Модуль — вертикальный срез `modules/<name>/` (backend + frontend + contracts) с
манифестом `module.yaml`. Правила, контракты и полный порядок действий — в
`docs/modules.md` (раздел «Как добавить модуль»); шаблон — `modules/_template/`.

Кратко:

1. Создайте каталог `modules/<name>/backend/` — Django-приложение; в `AppConfig`
   задайте `name = "modules.<name>.backend"` и явный `label` (он же — имя схемы
   БД). Моделям задайте `db_table` через
   `modules.common.backend.schemas.qualified_table`.
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

Единственная СУБД проекта — PostgreSQL; контейнер `db` поднимается вместе со
стеком разработки, а backend подключается к нему через `DATABASE_URL`
(см. `docs/adr/0002-postgresql-in-development.md`). Каждый модуль хранит данные в
своей схеме (`core`, `operations`, `common`); схемы создаются автоматически перед
миграциями, а ядро Django остаётся в `public`
(см. `docs/adr/0013-postgresql-schemas-per-module.md`).

### Подключение к базе

```bash
# Параметры по умолчанию — из docker-compose.yml / .env
docker compose exec db psql -U bankcashops -d bankcashops
```

### Сброс базы данных

```bash
docker compose down -v      # удаляет том postgres_data
docker compose up -d
```

### Резервная копия и восстановление

```bash
docker compose exec db pg_dump -U bankcashops bankcashops > backup.sql
docker compose exec -T db psql -U bankcashops -d bankcashops < backup.sql
```

Выгрузить данные одного модуля можно по его схеме:

```bash
docker compose exec db pg_dump -U bankcashops -n core bankcashops > core.sql
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
| Изменения в зависимостях не применяются | Пересоберите образы и обновите том `node_modules`: `docker compose up --build -d --renew-anon-volumes` |
