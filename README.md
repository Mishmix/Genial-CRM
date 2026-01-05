# CRM Bot

Telegram Business CRM с автоответчиком, Mini App и веб-интерфейсом.

## Возможности

- 📨 Автоматические ответы на входящие бизнес-сообщения
- 🌍 Определение языка (RU/EN/UA/ES) и ответ на языке клиента
- 👥 CRM для управления клиентами: статусы, теги, заметки
- 💬 Отправка сообщений клиентам прямо из CRM
- 🔍 Умный поиск с поддержкой опечаток и транслита
- 📱 Telegram Mini App + веб-версия
- 🔐 Безопасная авторизация (Telegram initData / пароль)

## Быстрый старт

### 1. Настройка окружения

```bash
cd "CRM BOT"
cp .env.example .env
```

Отредактируйте `.env`:

```env
# Обязательно
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_IDS=123456789  # Ваш Telegram ID

# Опционально
GROQ_API_KEY=your_groq_key  # Для улучшенного определения языка
ADMIN_PASSWORD_HASH=...     # Для входа через браузер
```

Сгенерировать хэш пароля:
```bash
python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your_password'))"
```

### 2. Запуск через Docker

```bash
docker compose up -d
```

Приложение будет доступно:
- Frontend: http://localhost
- Backend API: http://localhost:8000

### 3. Локальный запуск (разработка)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Настройка Telegram Bot

### 1. Создание бота

1. Откройте [@BotFather](https://t.me/BotFather)
2. Создайте бота: `/newbot`
3. Скопируйте токен в `.env`

### 2. Подключение к Business аккаунту

1. Откройте Telegram Settings → Telegram Business
2. В разделе "Chatbots" добавьте вашего бота
3. Бот начнёт получать бизнес-сообщения

### 3. Настройка Mini App

1. В BotFather: `/mybots` → выберите бота → Bot Settings → Menu Button
2. Укажите URL вашего приложения (нужен HTTPS)
3. Или создайте Web App: `/newapp`

### 4. Webhook (для продакшена)

```bash
# Установить webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram/webhook"

# Проверить
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## Структура проекта

```
CRM BOT/
├── backend/
│   ├── app/
│   │   ├── api/          # API роуты
│   │   ├── auth/         # Авторизация
│   │   ├── llm/          # Интеграция с Groq
│   │   ├── search/       # Поиск с транслитом
│   │   ├── telegram/     # Telegram bot
│   │   └── utils/        # Утилиты
│   ├── alembic/          # Миграции БД
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── auth/         # Контекст авторизации
│   │   ├── pages/        # Страницы
│   │   ├── components/   # Компоненты
│   │   └── telegram/     # Mini App SDK
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## API

### Авторизация

- `POST /api/auth/telegram` - Вход через Telegram initData
- `POST /api/auth/login` - Вход по паролю
- `POST /api/auth/logout` - Выход
- `GET /api/auth/me` - Текущий пользователь

### Клиенты

- `GET /api/clients` - Список клиентов
- `GET /api/clients/search?q=...` - Поиск
- `GET /api/clients/:id` - Детали клиента
- `PATCH /api/clients/:id` - Обновить статус/теги/заметки
- `POST /api/clients/:id/send` - Отправить сообщение
- `POST /api/clients/:id/read` - Отметить прочитанным

### Шаблоны

- `GET /api/templates` - Список шаблонов
- `POST /api/templates` - Создать шаблон

### Настройки

- `GET /api/settings` - Получить настройки
- `PUT /api/settings` - Обновить настройку

## Поиск

Поиск поддерживает:
- Опечатки (fuzzy matching)
- Транслитерацию: "Mikhail" найдёт "Михаил"
- Разные раскладки: "Vbhfbk" найдёт "Михаил"

## Безопасность

- Telegram Mini App: валидация initData + allowlist админов
- Браузер: bcrypt пароль + httpOnly cookie
- Секреты только через переменные окружения
- Логи без персональных данных

## Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| TELEGRAM_BOT_TOKEN | Токен бота | Да |
| ADMIN_TELEGRAM_IDS | ID админов (через запятую) | Да |
| GROQ_API_KEY | Ключ Groq API | Нет |
| ADMIN_PASSWORD_HASH | Bcrypt хэш пароля | Нет |
| PORTFOLIO_URL | URL портфолио | Нет |
| AUTO_REPLY_ENABLED | Включить автоответы | Нет |
| CORS_ORIGINS | Разрешённые origins | Нет |
| SESSION_SECRET | Секрет для сессий | Да |
| WEBHOOK_URL | URL для webhook | Нет |
| DATABASE_URL | URL базы данных | Нет |

## Лицензия

MIT
