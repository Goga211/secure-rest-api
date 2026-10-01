# secure-rest-api

Учебный REST API на Flask с упором на безопасность (ЛР1 по курсу «Информационная безопасность»,
ИТМО): JWT-аутентификация, хэширование паролей bcrypt, защита от SQL-инъекций и XSS, проверки
SAST и SCA в CI.

Стек: Python 3.12, Flask 3, SQLAlchemy 2 (SQLite), pydantic 2, bcrypt, PyJWT, Flask-Limiter,
pytest, ruff.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # и задать JWT_SECRET
flask --app wsgi init-db         # создать таблицы
flask --app wsgi create-user alice   # пароль спросит скрыто
flask --app wsgi run
```

Сгенерировать `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Переменные окружения (см. `.env.example`):

| Переменная | По умолчанию | Описание |
|---|---|---|
| `JWT_SECRET` | нет, обязательна | секрет подписи JWT, не короче 32 символов, иначе приложение не запустится |
| `DATABASE_URL` | `sqlite:///app.db` | строка подключения к БД |
| `JWT_TTL_MINUTES` | `15` | время жизни токена в минутах, от 1 до 1440 |
| `RATE_LIMIT_ENABLED` | `true` | ограничение частоты запросов к `/auth/login` |

Требования к учётным данным при `create-user`: логин 3-64 символа (латиница, цифры, точка,
дефис, подчёркивание, без учёта регистра), пароль не короче 12 символов и не длиннее 72 байт.

Тесты и проверки:

```bash
pip install -r requirements-dev.txt
pytest --cov          # тесты, покрытие не ниже 80%
ruff check .          # линтер
bandit -r app -ll     # SAST
pip-audit -r requirements.txt   # SCA
```

## Формат ответов

Все ответы, включая ошибки, приходят в одном JSON-конверте:

```json
{"success": true, "data": {...}, "error": null}
{"success": false, "data": null, "error": "Текст ошибки"}
```

## Эндпоинты

| Метод и путь | Доступ | Тело запроса | Успешный ответ |
|---|---|---|---|
| `GET /health` | всем | нет | 200, `{"status": "ok"}` |
| `POST /auth/login` | всем, не больше 5 запросов в минуту с одного IP | `{"username": str, "password": str}` | 200, `{"access_token", "token_type": "Bearer", "expires_in"}` |
| `GET /api/data` | с JWT | нет | 200, список последних 100 постов |
| `POST /api/posts` | с JWT | `{"title": str, "body": str}` | 201, созданный пост |

Пост в ответе: `{"id", "title", "body", "author", "created_at"}`. Поля `title`, `body` и
`author` экранированы для HTML, `created_at` в формате ISO 8601 (UTC). Автор поста берётся из
токена, задать его в теле запроса нельзя.

Ограничения на поля: `username` до 64 символов, `password` до 128 символов, `title` от 1 до
120 символов, `body` от 1 до 5000 символов. Лишние поля в теле запроса запрещены, типы не
приводятся (число вместо строки даёт 400).

### Коды ошибок

| Код | Когда |
|---|---|
| 400 | тело не JSON-объект, нет обязательных полей, неверный тип или длина, лишние поля |
| 401 | неверный логин или пароль; нет заголовка `Authorization`; токен поддельный, просроченный или выдан удалённому пользователю. Для `/api/*` в ответе заголовок `WWW-Authenticate: Bearer realm="api"` |
| 404 | неизвестный путь |
| 405 | неподдерживаемый метод, например `GET /auth/login` (в ответе заголовок `Allow`) |
| 413 | тело запроса больше 16 КБ |
| 429 | больше 5 попыток входа в минуту с одного IP |
| 500 | внутренняя ошибка; подробности только в логе сервера, клиенту общий текст |

## Примеры curl

Вход, ответ с токеном:

```bash
curl -s -X POST http://127.0.0.1:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "correct-horse-battery"}'
```

```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 900,
    "token_type": "Bearer"
  },
  "error": null,
  "success": true
}
```

Неверный пароль, тот же ответ, что и для несуществующего логина:

```json
{"data": null, "error": "Неверный логин или пароль", "success": false}
```

Запрос с токеном:

```bash
TOKEN="<access_token из ответа на вход>"
curl -s http://127.0.0.1:5000/api/data -H "Authorization: Bearer $TOKEN"
```

Запрос без токена, 401:

```bash
curl -si http://127.0.0.1:5000/api/data
```

```
HTTP/1.1 401 UNAUTHORIZED
WWW-Authenticate: Bearer realm="api"

{"data": null, "error": "Требуется заголовок Authorization: Bearer <token>", "success": false}
```

Создание поста, HTML в тексте возвращается экранированным:

```bash
curl -s -X POST http://127.0.0.1:5000/api/posts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Привет", "body": "<b>первый</b> пост"}'
```

```json
{
  "data": {
    "author": "alice",
    "body": "&lt;b&gt;первый&lt;/b&gt; пост",
    "created_at": "2026-10-01T20:21:01.217563+00:00",
    "id": 1,
    "title": "Привет"
  },
  "error": null,
  "success": true
}
```

## Меры защиты

| Угроза | Мера | Где в коде | Тесты |
|---|---|---|---|
| SQL-инъекции | только ORM SQLAlchemy: значения уходят в драйвер связанными параметрами, SQL из строк не собирается | `app/models.py`, `app/auth/users.py`, `app/api/routes.py` | `tests/test_sqli.py` |
| XSS | `title`, `body`, `author` экранируются на выходе (`markupsafe.escape`), в БД хранится исходный текст; CSP `default-src 'none'` и `X-Content-Type-Options: nosniff` | `app/api/serializers.py`, `app/security.py` | `tests/test_xss.py` |
| Утечка паролей | только хэш bcrypt (12 раундов, соль в хэше); пароли длиннее 72 байт отклоняются явно, потому что bcrypt молча обрезает лишнее | `app/auth/passwords.py` | `tests/test_passwords.py` |
| Подделка токена | JWT HS256, список алгоритмов задан жёстко (токен с `alg: none` не пройдёт), обязательны claims `sub`, `iss`, `iat`, `exp`, проверяется издатель; срок жизни 15 минут; пользователь из токена проверяется в БД | `app/auth/tokens.py`, `app/auth/decorators.py` | `tests/test_tokens.py`, `tests/test_jwt_required.py` |
| Подбор логинов | один ответ 401 для неверного логина и неверного пароля; для несуществующего логина пароль сверяется с хэшем-заглушкой, чтобы время ответа не отличалось | `app/auth/routes.py`, `app/auth/passwords.py` | `tests/test_login.py` |
| Перебор паролей | не больше 5 попыток входа в минуту с одного IP (Flask-Limiter), сверх лимита 429 | `app/auth/routes.py`, `app/extensions.py` | `tests/test_rate_limit.py` |
| Некорректный ввод, mass assignment | схемы pydantic: `strict` (без приведения типов), `extra="forbid"` (лишние поля вроде `role` или `author` запрещены), ограничения длины | `app/auth/schemas.py`, `app/api/schemas.py` | `tests/test_login.py`, `tests/test_api_posts.py` |
| Большие запросы | тело больше 16 КБ отклоняется с 413 | `app/__init__.py` | `tests/test_api_posts.py`, `tests/test_errors.py` |
| Утечка деталей ошибок | все ошибки в общем JSON-конверте, на 500 клиент получает общий текст, трейсбек только в лог | `app/errors.py` | `tests/test_errors.py` |
| Кликджекинг, MIME-sniffing, утечка Referer, кэширование | заголовки `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` на всех ответах, включая ошибки | `app/security.py` | `tests/test_security_headers.py` |
| Утечка секретов | секреты только из переменных окружения, `.env` в `.gitignore`; `JWT_SECRET` короче 32 символов не даёт запустить приложение; секрет не попадает в `repr` настроек | `app/config.py` | `tests/test_config.py` |

Всего 122 теста, покрытие 100% (минимум для CI 80%).

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) запускается на каждый push и pull request, права
токена только на чтение. Четыре независимых job:

| Job | Инструмент | Что проверяет | Когда падает | Артефакт |
|---|---|---|---|---|
| Тесты и линтер | ruff, pytest | стиль и ошибки кода (в том числе правила безопасности `S` из bandit), формат, тесты | замечание ruff, упавший тест, покрытие ниже 80% | `coverage` |
| SAST (bandit) | bandit | исходный код `app/`: опасные вызовы, захардкоженные секреты, небезопасные функции | находка уровня medium и выше | `bandit-report` (HTML) |
| SCA (pip-audit) | pip-audit | зависимости из `requirements.txt` по базе уязвимостей PyPI | любая известная уязвимость | `pip-audit-report` (JSON) |
| SCA (OWASP Dependency-Check) | Dependency-Check | зависимости по базе NVD | уязвимость с CVSS 7.0 и выше | `dependency-check-report` (HTML) |

Где смотреть отчёты: вкладка **Actions** репозитория → нужный запуск workflow **CI** → блок
**Artifacts** внизу страницы запуска. Ключ NVD для Dependency-Check хранится в секрете
репозитория `NVD_API_KEY`.

### Скриншоты отчётов

Скриншоты отчётов bandit, pip-audit и Dependency-Check добавит автор.

## Сравнение pip-audit и OWASP Dependency-Check

| | pip-audit | OWASP Dependency-Check |
|---|---|---|
| Источник данных | база уязвимостей PyPI (PyPA Advisory Database), по желанию OSV | NVD (база CVE), сопоставление по идентификаторам CPE |
| Как находит пакет | точное имя и версия пакета PyPI | по имени подбираются CPE, для PyJWT их два: `pyjwt_project:pyjwt` и `jwt_project:jwt` |
| Поддержка Python | основная задача инструмента | анализаторы Python экспериментальные, нужен флаг `--enableExperimental` |
| Скорость в CI | около 30 секунд вместе с установкой зависимостей | около 30 секунд: action использует заранее скачанную базу (`--noupdate`); без неё первое скачивание NVD занимает десятки минут |
| Ложные срабатывания | мало: база ведётся по пакетам PyPI | больше: CPE совпадают неточно, в NVD попадают оспоренные CVE |
| Результат в этом проекте | 23 пакета, уязвимостей не найдено | CVE-2025-45770 в PyJWT 2.15.0, CVSS 7.0 |

**Разбор CVE-2025-45770.** Dependency-Check остановил CI на CVE-2025-45770 («слабое
шифрование» в PyJWT), а pip-audit её не нашёл. CVE оспорена: мейнтейнеры PyJWT считают, что
длину ключа HMAC выбирает приложение, а не библиотека, поэтому в базах PyPI и OSV её нет. В
этом проекте риск закрыт: `JWT_SECRET` короче 32 символов (256 бит, минимум для HS256 по
RFC 7518) не даёт запустить приложение. CVE подавлена в `dependency-check-suppressions.xml`
с этим обоснованием, остальные находки Dependency-Check по-прежнему останавливают CI.

**Вывод.** Инструменты дополняют друг друга. pip-audit точнее для Python и почти не даёт ложных
срабатываний, Dependency-Check шире по охвату (NVD, другие экосистемы), но требует разбора
находок и подавлений с обоснованием. bandit по коду `app/` (463 строки) замечаний не нашёл.

## Известные ограничения

- **Токены нельзя отозвать до истечения срока.** Нет выхода из системы и чёрного списка
  токенов, украденный токен действует до 15 минут. Смягчение: короткий TTL.
- **SQLite и `create_all` без миграций.** Подходит для учебного проекта; для продакшена нужна
  серверная СУБД и миграции (Alembic).
- **Лимитер хранит счётчики в памяти процесса.** Сбрасывается при перезапуске, не работает
  между несколькими процессами или серверами; за обратным прокси все клиенты получат IP
  прокси, нужен `ProxyFix` и общее хранилище (Redis).
- **Нет HTTPS в самом приложении.** Встроенный сервер Flask только для разработки, в
  продакшене API должен работать за обратным прокси с TLS.
- **Пользователи создаются только через CLI.** Эндпоинта регистрации и смены пароля нет.
- **Подавление CVE-2025-45770 нужно пересматривать** при обновлении PyJWT или изменении статуса
  CVE.
