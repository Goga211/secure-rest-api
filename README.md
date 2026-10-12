# secure-rest-api

[![CI](https://github.com/Goga211/secure-rest-api/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Goga211/secure-rest-api/actions/workflows/ci.yml?query=branch%3Amain)

REST API на Flask с защитой от типовых уязвимостей: JWT-аутентификация, хэширование паролей
bcrypt, защита от SQL-инъекций и XSS, проверки SAST и SCA в CI.

Стек: Python 3.12, Flask 3, SQLAlchemy 2 (SQLite), pydantic 2, bcrypt, PyJWT, Flask-Limiter,
pytest, ruff.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env, затем задать JWT_SECRET в .env
flask --app wsgi init-db         # создать таблицы
flask --app wsgi create-user alice   # пароль спросит скрыто
flask --app wsgi run
```

Сгенерировать `JWT_SECRET` (только так, а не вручную: стойкость секрета даёт случайность, а не
длина):

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
ruff format --check . # формат, включая python-блоки в README
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

`POST /auth/login` и `GET /api/data` заданы в лабораторной, `POST /api/posts` это третий метод
на выбор: через него в базу попадает пользовательский текст, на котором видна защита от XSS.

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

JSON в ответах ниже отформатирован для читаемости. Сервер отдаёт его в одну строку, а кириллицу
кодирует как `\uXXXX` (стандартное поведение Flask), по смыслу это тот же JSON.

Вход, ответ с токеном (токен сокращён):

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

Запрос без токена, 401 (заголовки `Server`, `Date`, `Content-Length`, `Connection` опущены):

```bash
curl -si http://127.0.0.1:5000/api/data
```

```
HTTP/1.1 401 UNAUTHORIZED
Content-Type: application/json
WWW-Authenticate: Bearer realm="api"
X-Content-Type-Options: nosniff
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store

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

### SQL-инъекции (OWASP A03 Injection)

Все запросы к БД идут через ORM SQLAlchemy, SQL из строк нигде не собирается. Значение из
запроса попадает в драйвер SQLite связанным параметром, поэтому `' OR '1'='1' --` остаётся
обычной строкой и сравнивается с логином целиком:

```python
# app/auth/users.py
def find_user(username: str) -> User | None:
    statement = db.select(User).filter_by(username=normalize_username(username))
    return db.session.execute(statement).scalar_one_or_none()
```

SQLAlchemy превращает это в `SELECT ... FROM users WHERE users.username = ?`, значение уходит
отдельно от текста запроса. Посты создаются так же, через `Post(title=..., body=...)` и
`db.session.add`. В `tests/test_sqli.py` в логин подставляются `' OR '1'='1' --`, `admin'--` и
`UNION SELECT`, в пароль `' OR '1'='1' --` и `' OR 1=1 --` (ответ 401, токена нет), а заголовок поста
`'); DROP TABLE posts; --` сохраняется как текст, таблица остаётся на месте.

### XSS (OWASP A03 Injection)

Пользовательские поля экранируются на выходе функцией `markupsafe.escape` (её же использует
Jinja2 во Flask). В БД лежит исходный текст, а в ответе `<`, `>`, `&`, `"`, `'` заменены на
HTML-сущности:

```python
# app/api/serializers.py
def post_to_dict(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "title": _escape_html(post.title),
        "body": _escape_html(post.body),
        "author": _escape_html(post.author.username),
        "created_at": _iso_utc(post.created_at),
    }


def _escape_html(text: str) -> str:
    return str(escape(text))
```

Если клиент вставит ответ в страницу, `<script>alert(1)</script>` покажется как текст и не
выполнится. Вторая линия защиты: заголовки `Content-Security-Policy: default-src 'none'` и
`X-Content-Type-Options: nosniff`, чтобы браузер не исполнил JSON-ответ как HTML или скрипт.
Тесты: `tests/test_xss.py`.

### Аутентификация (OWASP A07, A02, A01)

Пароли хранятся только как хэш bcrypt (12 раундов, случайная соль внутри хэша). Пользователь
создаётся командой `flask create-user`, пароль вводится скрыто и в открытом виде нигде не
сохраняется.

Как проходит вход и запрос к защищённому эндпоинту:

1. `POST /auth/login`: pydantic проверяет тело (только `username` и `password`, только строки).
   Flask-Limiter пропускает не больше 5 попыток в минуту с одного IP.
2. Пользователь ищется в БД, пароль сверяется через `bcrypt.checkpw`. Если логина нет, пароль
   всё равно сверяется с хэшем-заглушкой: время ответа одинаковое, и по нему не понять,
   существует ли логин. Ответ на неверный логин и неверный пароль тоже одинаковый.
3. При успехе выдаётся JWT, подписанный HS256 секретом `JWT_SECRET` из окружения. В токене
   `sub` (id пользователя), `iss` (`secure-rest-api`), `iat` и `exp` (через 15 минут).
4. Клиент передаёт токен в заголовке `Authorization: Bearer <token>`.
5. Декоратор `jwt_required` на каждом маршруте `/api/*` достаёт токен и проверяет подпись,
   алгоритм (только HS256, токен с `alg: none` отклоняется), срок, издателя и наличие всех
   claims. Затем находит пользователя в БД: токен удалённого пользователя не действует.
6. Любая ошибка проверки даёт 401 с `WWW-Authenticate: Bearer realm="api"`. При успехе
   пользователь кладётся в `g.current_user`, автор поста берётся оттуда, а не из тела запроса.

```python
# app/auth/tokens.py
payload = jwt.decode(
    token,
    secret,
    algorithms=[JWT_ALGORITHM],  # "HS256", алгоритм из заголовка токена не используется
    issuer=JWT_ISSUER,
    options={"require": REQUIRED_CLAIMS},  # sub, iss, iat, exp
)
```

Проверка JWT сделана декоратором `jwt_required`, а не глобальным middleware: публичные маршруты
(`/health`, `/auth/login`) должны оставаться без проверки, а декоратор виден прямо на маршруте.
Риск забыть декоратор закрыт тестом `tests/test_api_auth_coverage.py`: он обходит все
зарегистрированные маршруты `/api/*` и требует 401 без токена.

### Все меры

| Угроза | OWASP Top 10 2021 | Мера | Где в коде | Тесты |
|---|---|---|---|---|
| SQL-инъекции | A03 | только ORM SQLAlchemy: значения уходят в драйвер связанными параметрами, SQL из строк не собирается | `app/models.py`, `app/auth/users.py`, `app/api/routes.py` | `tests/test_sqli.py` |
| XSS | A03 | `title`, `body`, `author` экранируются на выходе (`markupsafe.escape`), в БД хранится исходный текст; CSP `default-src 'none'` и `X-Content-Type-Options: nosniff` | `app/api/serializers.py`, `app/security.py` | `tests/test_xss.py` |
| Утечка паролей | A02 | только хэш bcrypt (12 раундов, соль в хэше); пароли длиннее 72 байт отклоняются явно, потому что bcrypt молча обрезает лишнее | `app/auth/passwords.py` | `tests/test_passwords.py` |
| Подделка токена | A07, A02 | JWT HS256, список алгоритмов задан жёстко (токен с `alg: none` не пройдёт), обязательны claims `sub`, `iss`, `iat`, `exp`, проверяется издатель; срок жизни 15 минут; пользователь из токена проверяется в БД | `app/auth/tokens.py`, `app/auth/decorators.py` | `tests/test_tokens.py`, `tests/test_jwt_required.py` |
| Незащищённый эндпоинт | A01 | декоратор `jwt_required` на каждом маршруте `/api/*`; тест обходит все зарегистрированные маршруты `/api/*` и требует 401 без токена, поэтому эндпоинт без декоратора роняет CI | `app/api/routes.py` | `tests/test_api_auth_coverage.py` |
| Подбор логинов | A07 | один ответ 401 для неверного логина и неверного пароля; для несуществующего логина пароль сверяется с хэшем-заглушкой, чтобы время ответа не отличалось | `app/auth/routes.py`, `app/auth/passwords.py` | `tests/test_login.py` |
| Перебор паролей | A07 | не больше 5 попыток входа в минуту с одного IP (Flask-Limiter), сверх лимита 429 | `app/auth/routes.py`, `app/extensions.py` | `tests/test_rate_limit.py` |
| Некорректный ввод, mass assignment | A03, A08 | схемы pydantic: `strict` (без приведения типов), `extra="forbid"` (лишние поля вроде `role` или `author` запрещены), ограничения длины | `app/auth/schemas.py`, `app/api/schemas.py` | `tests/test_login.py`, `tests/test_api_posts.py` |
| Большие запросы | вне Top 10 (CWE-770) | тело больше 16 КБ отклоняется с 413 | `app/__init__.py` | `tests/test_api_posts.py`, `tests/test_errors.py` |
| Утечка деталей ошибок | A04 (CWE-209) | все ошибки в общем JSON-конверте, на 500 клиент получает общий текст, трейсбек только в лог | `app/errors.py` | `tests/test_errors.py` |
| Кликджекинг, MIME-sniffing, утечка Referer, кэширование | A05 | заголовки `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` на всех ответах, включая ошибки | `app/security.py` | `tests/test_security_headers.py` |
| Утечка секретов | A07 (CWE-798), A02 | секреты только из переменных окружения, `.env` в `.gitignore`; `JWT_SECRET` генерируется случайно (`secrets.token_urlsafe(48)`), а значение короче 32 символов не даёт запустить приложение; секрет не попадает в `repr` настроек | `app/config.py` | `tests/test_config.py` |

Всего 124 теста, покрытие 100% (минимум для CI 80%).

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) запускается на каждый push и pull request, права
токена только на чтение. Четыре независимых job:

| Job | Инструмент | Что проверяет | Когда падает | Артефакт |
|---|---|---|---|---|
| Тесты и линтер | ruff, pytest | стиль и ошибки кода (в том числе правила безопасности `S`, аналог bandit в ruff), формат, тесты | замечание ruff, упавший тест, покрытие ниже 80% | `coverage` |
| SAST (bandit) | bandit | исходный код `app/`: опасные вызовы, захардкоженные секреты, небезопасные функции | находка уровня medium и выше | `bandit-report` (HTML) |
| SCA (pip-audit) | pip-audit | зависимости из `requirements.txt` по базе уязвимостей PyPI | любая известная уязвимость | `pip-audit-report` (JSON) |
| SCA (OWASP Dependency-Check) | Dependency-Check | зависимости по базе NVD | уязвимость с CVSS 7.0 и выше | `dependency-check-report` (HTML) |

Последний успешный запуск pipeline: [успешные запуски ветки main](https://github.com/Goga211/secure-rest-api/actions/workflows/ci.yml?query=branch%3Amain+is%3Asuccess),
верхний в списке. Каждый push в README запускает CI заново, поэтому постоянная ссылка ведёт на
отфильтрованный список, а не на конкретный номер.

Где смотреть отчёты: вкладка **Actions** репозитория → нужный запуск workflow **CI** → блок
**Artifacts** внизу страницы запуска. Секреты в workflow не используются, поэтому все проверки
работают и в pull request из форков.

Защита самого pipeline: сторонний action Dependency-Check закреплён по SHA коммита, а не по
плавающей ветке, и секреты ему не передаются; раннер зафиксирован (`ubuntu-24.04`); `checkout` не
сохраняет токен CI в `.git` (`persist-credentials: false`), а у самого токена только право
на чтение.

### Скриншоты отчётов

Запуск CI #21 (коммит `c56e8e0`): все четыре job прошли успешно, сохранено 4 артефакта.

![Запуск CI](docs/screenshots/ci-run.png)

**SAST, bandit** (`bandit-report.html`): 463 строки кода, замечаний уровня medium и выше нет.
Одно замечание уровня low, B105 «возможный захардкоженный пароль» на строку `"token_type":
"Bearer"` в `app/auth/routes.py`. Это ложное срабатывание: `Bearer` это тип токена по
RFC 6750, а не пароль. CI падает только на medium и выше (`-ll`), поэтому замечание не
блокирует сборку, но остаётся в отчёте.

![Отчёт bandit](docs/screenshots/bandit-report.png)

**SCA, OWASP Dependency-Check** (`dependency-check-report.html`): проверено 26 зависимостей,
уязвимых 0, одна уязвимость подавлена с обоснованием (CVE-2025-45770, разбор ниже).

![Отчёт Dependency-Check](docs/screenshots/dependency-check-report.png)

**SCA, pip-audit** (`pip-audit-report.json`): проверено 22 пакета, уязвимостей нет:

```json
{"dependencies": [{"name": "annotated-types", "version": "0.8.0", "vulns": []},
  {"name": "bcrypt", "version": "5.0.0", "vulns": []},
  ...
  {"name": "pyjwt", "version": "2.15.0", "vulns": []},
  ...
  {"name": "werkzeug", "version": "3.1.9", "vulns": []}], "fixes": []}
```

Лог job pip-audit в том же запуске:

```
No known vulnerabilities found
```

### Найдено и исправлено: CVE-2026-102598 в Werkzeug

pip-audit остановил [запуск CI #20](https://github.com/Goga211/secure-rest-api/actions/runs/38223336152)
(коммит `b133ead`): в зависимостях была уязвимая версия Werkzeug. Остальные три job в этом
запуске прошли, Dependency-Check сборку не остановил. [Лог job pip-audit](https://github.com/Goga211/secure-rest-api/actions/runs/38223336152/job/114724682982):

```
Found 1 known vulnerability in 1 package
Name     Version ID              Fix Versions
-------- ------- --------------- ------------
werkzeug 3.1.8   CVE-2026-102598 3.1.9
##[error]Process completed with exit code 1.
```

Исправление: в `requirements.txt` Werkzeug поднят до 3.1.9, где уязвимость закрыта (коммит
`c56e8e0`). Тесты на новой версии прошли без изменений кода, и
[запуск CI #21](https://github.com/Goga211/secure-rest-api/actions/runs/38223765166) прошёл
полностью, со скриншотов выше. Так pipeline и должен работать: уязвимость в зависимости
появилась в базе после того, как код был готов, и CI заблокировал сборку до обновления.

## Сравнение pip-audit и OWASP Dependency-Check

| | pip-audit | OWASP Dependency-Check |
|---|---|---|
| Источник данных | база уязвимостей PyPI (PyPA Advisory Database), по желанию OSV | NVD (база CVE), сопоставление по идентификаторам CPE |
| Как находит пакет | точное имя и версия пакета PyPI | по имени подбираются CPE, для PyJWT их два: `pyjwt_project:pyjwt` и `jwt_project:jwt` |
| Поддержка Python | основная задача инструмента | анализаторы Python экспериментальные, нужен флаг `--enableExperimental` |
| Скорость в CI | около 40 секунд вместе с установкой зависимостей | около 30 секунд, сам анализ несколько секунд: action запускает сканер с `--noupdate` и берёт базу NVD, уже собранную в его Docker-образе, ключ NVD не нужен |
| Ложные срабатывания | мало: база ведётся по пакетам PyPI | больше: CPE совпадают неточно, в NVD попадают оспоренные CVE |
| Результат в этом проекте | 22 пакета, уязвимостей не найдено | 26 зависимостей, CVE-2025-45770 в PyJWT 2.15.0 (CVSS 7.0), подавлена с обоснованием |

**Разбор CVE-2025-45770.** Dependency-Check остановил CI на CVE-2025-45770 («слабое
шифрование» в PyJWT), а pip-audit её не нашёл. CVE оспорена: длину ключа HMAC выбирает
приложение, а не библиотека, поэтому в базах PyPI и OSV её нет. В этом проекте стойкость ключа
обеспечивает случайная генерация: `secrets.token_urlsafe(48)` даёт 48 случайных байт, то есть
384 бита энтропии при минимуме 256 бит для HS256 по RFC 7518. Проверка в `Settings` только
отсекает значения короче 32 символов: от слабого, но длинного секрета вроде `"a" * 32` она
не защищает, поэтому секрет нужно генерировать командой из раздела «Локальный запуск», а не
придумывать. CVE подавлена в `dependency-check-suppressions.xml` с этим обоснованием, остальные находки Dependency-Check по-прежнему останавливают CI.

**Вывод.** Инструменты дополняют друг друга. pip-audit точнее для Python и почти не даёт ложных
срабатываний, Dependency-Check шире по охвату (NVD, другие экосистемы), но требует разбора
находок и подавлений с обоснованием. bandit по коду `app/` (463 строки) нашёл одно ложное
замечание уровня low, разобранное выше.

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
- **Образ внутри Dependency-Check action не закреплён.** Сам action закреплён по SHA, но его
  Dockerfile собирается из `owasp/dependency-check-action:latest`; полностью воспроизводимой
  сборки это не даёт. Из того же образа берётся база NVD (action запускает сканер с
  `--noupdate`), поэтому её свежесть зависит от того, когда был собран образ.

## Ответы на контрольные вопросы

**1. Почему bcrypt лучше SHA-256 для паролей?** SHA-256 сделан быстрым: на GPU это миллиарды
хэшей в секунду, поэтому утёкшую базу можно перебрать по словарю. bcrypt медленный намеренно, и
скорость настраивается числом раундов (здесь 12, то есть 2^12 итераций), а ещё ему нужна память,
что мешает перебору на GPU. Случайная соль хранится в самом хэше, поэтому одинаковые пароли дают
разные хэши, и радужные таблицы не работают. Голый SHA-256 соли не добавляет.

**2. Чем SAST отличается от DAST?** SAST анализирует исходный код без запуска (здесь bandit и
правила `S` в ruff): находит опасные вызовы и захардкоженные секреты рано, прямо в CI, но не
видит конфигурацию и поведение работающего приложения и даёт ложные срабатывания. DAST атакует
запущенное приложение снаружи, как чёрный ящик (например, OWASP ZAP): находит то, что видно
только во время работы (заголовки, обработку сессий, ошибки конфигурации), но не показывает
строку кода с проблемой и требует развёрнутого стенда.

**3. Как работает JWT?** Токен состоит из трёх частей в Base64URL через точку: заголовок
(`{"alg": "HS256", "typ": "JWT"}`), payload с claims (здесь `sub`, `iss`, `iat`, `exp`) и
подпись HMAC-SHA256 от первых двух частей на секрете сервера. Payload не шифруется, его может
прочитать кто угодно, поэтому секретов в нём нет. Сервер заново считает подпись своим
секретом и сравнивает с подписью в токене: если payload изменили, подпись не совпадёт. Затем
проверяет алгоритм (только HS256), срок `exp` и издателя `iss`. Состояние на сервере не
хранится, поэтому отозвать токен до истечения срока нельзя (см. ограничения).

**4. Чем опасно не проверять зависимости?** Большая часть кода приложения это сторонние
библиотеки, и уязвимость в любой из них становится уязвимостью приложения (OWASP A06
Vulnerable and Outdated Components): пример в этом проекте, CVE-2026-102598 в Werkzeug. Без
аудита такие CVE остаются в продакшене месяцами, к тому же можно получить вредоносный или
подменённый пакет (supply chain). Поэтому в CI два SCA-сканера, версии закреплены в
`requirements.txt`, и сборка падает на известной уязвимости.
