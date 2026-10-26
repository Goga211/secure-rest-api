# secure-rest-api

[![CI](https://github.com/Goga211/secure-rest-api/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Goga211/secure-rest-api/actions/workflows/ci.yml?query=branch%3Amain)

REST API на Flask с защитой от SQL-инъекций, XSS и атак на аутентификацию (OWASP Top 10).
Вход по логину и паролю (хэш bcrypt), доступ к данным по JWT. На каждый push и pull request
GitHub Actions запускает тесты, SAST (bandit) и SCA (pip-audit, OWASP Dependency-Check).

Стек: Python 3.12, Flask 3, SQLAlchemy 2 (SQLite), pydantic 2, bcrypt, PyJWT, Flask-Limiter.

Подробная версия с разбором каждой меры, находок сканеров и ответами на контрольные вопросы:
[docs/details.md](docs/details.md).

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # задать в .env JWT_SECRET, команда ниже
flask --app wsgi init-db
flask --app wsgi create-user alice   # пароль спросит скрыто
flask --app wsgi run
```

Секрет генерируется так (короче 32 символов приложение не запустится):
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Проверки локально: `pip install -r requirements-dev.txt`, затем `pytest --cov`, `ruff check .`,
`bandit -r app -ll`, `pip-audit -r requirements.txt`.

## API

| Метод и путь | Доступ | Тело запроса | Ответ |
|---|---|---|---|
| `POST /auth/login` | всем, не больше 5 попыток в минуту с одного IP | `{"username", "password"}` | 200, `{"access_token", "token_type": "Bearer", "expires_in": 900}` |
| `GET /api/data` | только с JWT | нет | 200, последние 100 постов |
| `POST /api/posts` | только с JWT | `{"title", "body"}` | 201, созданный пост |
| `GET /health` | всем | нет | 200, `{"status": "ok"}` |

`POST /api/posts` это третий метод на выбор: через него в базу попадает пользовательский текст,
на нём видна защита от XSS. Все ответы приходят в конверте `{"success", "data", "error"}`.
Ошибки: 400 (некорректное тело), 401 (нет токена, неверный токен, неверный логин или пароль),
404, 405, 413 (тело больше 16 КБ), 429 (превышен лимит входа), 500 (без деталей).

## Проверка через curl

```bash
# вход, в ответе токен
curl -s -X POST http://127.0.0.1:5000/auth/login -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "correct-horse-battery"}'
# {"data": {"access_token": "eyJhbGciOiJIUzI1NiIs...", "expires_in": 900, "token_type": "Bearer"}, ...}

# без токена: 401
curl -si http://127.0.0.1:5000/api/data
# HTTP/1.1 401 UNAUTHORIZED
# WWW-Authenticate: Bearer realm="api"

# с токеном: 200 и список постов
curl -s http://127.0.0.1:5000/api/data -H "Authorization: Bearer $TOKEN"

# HTML в посте возвращается экранированным
curl -s -X POST http://127.0.0.1:5000/api/posts -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"title": "Hello", "body": "<b>first</b> post"}'
# {"data": {"author": "alice", "body": "&lt;b&gt;first&lt;/b&gt; post", ...}, ...}
```

Неверный логин и неверный пароль дают один и тот же ответ: 401 «Неверный логин или пароль».
Шестая попытка входа за минуту получает 429.

## Меры защиты

### SQL-инъекции

Все запросы к БД идут через ORM SQLAlchemy, SQL из строк не собирается. ORM строит
параметризованный запрос `WHERE users.username = ?`, а значение передаёт драйверу отдельно, как
данные. Ввод `' OR '1'='1' --` ищется как обычный логин и не находится.

```python
def find_user(username: str) -> User | None:
    statement = db.select(User).filter_by(username=normalize_username(username))
    return db.session.execute(statement).scalar_one_or_none()
```

Тесты `tests/test_sqli.py`: `' OR '1'='1' --`, `UNION SELECT` и `DROP TABLE` в логине, пароле и
посте.

### XSS

Поля `title`, `body` и `author` экранируются на выходе через `markupsafe.escape` (та же функция,
что в шаблонах Flask): `<` становится `&lt;`, `>` становится `&gt;`, так же `&`, `"` и `'`.
Браузер покажет такой текст, но не выполнит. В БД хранится исходный текст.

```python
def post_to_dict(post: Post) -> dict[str, Any]:
    # Экранируем на выходе, а не на входе: в БД лежит исходный текст
    return {
        "id": post.id,
        "title": _escape_html(post.title),
        "body": _escape_html(post.body),
        "author": _escape_html(post.author.username),
        "created_at": _iso_utc(post.created_at),
    }
```

Дополнительно на всех ответах стоят заголовки `Content-Security-Policy: default-src 'none'`,
`X-Content-Type-Options: nosniff` и `X-Frame-Options: DENY`. API рассчитан на веб-клиент:
клиенту, который выводит текст не в HTML, придётся раскодировать `&lt;`.

Тесты: `tests/test_xss.py`, `tests/test_security_headers.py`.

### Аутентификация

**Пароли.** В БД хранится только хэш bcrypt: 12 раундов (2^12 итераций), случайная соль внутри
хэша. Пароли длиннее 72 байт отклоняются явно, потому что bcrypt молча обрезает лишнее.

```python
def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(...)
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")
```

**JWT.** После входа выдаётся токен HS256 на 15 минут с claims `sub` (id пользователя), `iss`,
`iat` и `exp`. Секрет `JWT_SECRET` берётся только из переменной окружения. Проверка токена:

```python
payload = jwt.decode(
    token,
    secret,
    algorithms=[JWT_ALGORITHM],  # только HS256, алгоритм из заголовка токена не используется
    issuer=JWT_ISSUER,
    options={"require": REQUIRED_CLAIMS},  # sub, iss, iat, exp обязательны
)
```

Проверяются подпись, алгоритм (токен с `alg: none` не пройдёт), срок действия, издатель и то, что
пользователь из токена ещё есть в БД. Любая ошибка даёт 401.

**Middleware.** Токен проверяет декоратор `jwt_required`. Он стоит на каждом маршруте `/api/*` и
выполняется до кода эндпоинта, а `/health` и `/auth/login` остаются открытыми:

```python
@api_bp.get("/data")
@jwt_required
def list_posts() -> Response: ...
```

Чтобы декоратор не забыли на новом эндпоинте, тест `tests/test_api_auth_coverage.py` обходит все
маршруты `/api/*` и требует 401 без токена. Сравнение с `api_bp.before_request` есть в
[docs/details.md](docs/details.md).

**Вход.** Не больше 5 попыток в минуту с одного IP (Flask-Limiter), дальше 429. Для
несуществующего логина пароль всё равно сверяется с хэшем-заглушкой, чтобы по времени ответа
нельзя было понять, существует ли логин.

Тесты: `tests/test_passwords.py`, `tests/test_tokens.py`, `tests/test_jwt_required.py`,
`tests/test_login.py`, `tests/test_rate_limit.py`.

### Остальное

- Тело запроса проверяется схемами pydantic: лишние поля (`author`, `role`) и неверные типы дают
  400, автор поста берётся только из токена.
- Тело больше 16 КБ отклоняется с 413.
- На 500 клиент получает общий текст, трейсбек пишется только в лог.

Всего 124 теста, покрытие 100% (CI требует не меньше 80%).

## CI/CD

`.github/workflows/ci.yml` запускается на каждый push и pull request:

| Job | Инструмент | Падает, если |
|---|---|---|
| Тесты и линтер | pytest, ruff | упал тест, покрытие ниже 80%, есть замечание линтера, `requirements.txt` не совпадает с `requirements.in` |
| SAST | bandit | находка уровня medium и выше |
| SCA | pip-audit | любая известная уязвимость в зависимостях |
| SCA | OWASP Dependency-Check | уязвимость с CVSS 7.0 и выше |

Отчёты сохраняются в артефакты запуска: Actions, нужный запуск, блок Artifacts.

**Последний успешный запуск:** [успешные запуски ветки main](https://github.com/Goga211/secure-rest-api/actions/workflows/ci.yml?query=branch%3Amain+is%3Asuccess),
верхний в списке. Скриншоты ниже сняты с [запуска CI #30](https://github.com/Goga211/secure-rest-api/actions/runs/40289762760).

![Запуск CI](docs/screenshots/ci-run.png)

**bandit:** 463 строки кода, замечаний уровня medium и выше нет. Одно замечание low (B105) на
строку `"token_type": "Bearer"`: ложное срабатывание, это тип токена, а не пароль.

![Отчёт bandit](docs/screenshots/bandit-report.png)

**OWASP Dependency-Check:** 26 зависимостей, уязвимых 0.

![Отчёт Dependency-Check](docs/screenshots/dependency-check-report.png)

**pip-audit:** 22 пакета, `No known vulnerabilities found`.

### Найдено и исправлено: CVE в Werkzeug

pip-audit остановил [запуск CI #20](https://github.com/Goga211/secure-rest-api/actions/runs/38223336152):
в Werkzeug 3.1.8 нашлась CVE-2026-102598.

```
Name     Version ID              Fix Versions
-------- ------- --------------- ------------
werkzeug 3.1.8   CVE-2026-102598 3.1.9
```

Werkzeug обновлён до 3.1.9, и [запуск CI #21](https://github.com/Goga211/secure-rest-api/actions/runs/38223765166)
прошёл. Уязвимость появилась в базе уже после того, как код был готов, и pipeline сам заблокировал
сборку.

Dependency-Check раньше находил в PyJWT CVE-2025-45770 о слабом ключе. CVE оспорена, а ключ здесь
случайный (384 бита), поэтому она подавлена с обоснованием в `dependency-check-suppressions.xml`.
Сейчас Dependency-Check её не находит, почему, описано в [docs/details.md](docs/details.md).

## Зависимости

Прямые зависимости перечислены в `requirements.in`. Полный список с транзитивными,
`requirements.txt`, генерирует uv, руками он не правится:

```bash
uv pip compile requirements.in --universal --python-version 3.12 --no-annotate -o requirements.txt
```

CI проверяет, что `requirements.txt` актуален. Сканеры проверяют именно его.

## Ограничения

- Токен нельзя отозвать до истечения 15 минут: нет выхода и чёрного списка токенов.
- Счётчики лимита входа хранятся в памяти процесса; за прокси нужны `ProxyFix` и Redis.
- В самом приложении нет HTTPS, в продакшене нужен прокси с TLS.
- SQLite без миграций, пользователи создаются только через CLI.
- В lock-файле нет хэшей пакетов.
