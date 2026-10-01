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
