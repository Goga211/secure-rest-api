# secure-rest-api

Учебный REST API на Flask с упором на безопасность: JWT-аутентификация,
хэширование паролей bcrypt, защита от SQL-инъекций и XSS, проверки SAST/SCA в CI.

Проект в разработке, описание API и мер защиты появится по мере готовности.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # и задать JWT_SECRET
flask --app wsgi run
```

Проверка: `curl http://127.0.0.1:5000/health`
