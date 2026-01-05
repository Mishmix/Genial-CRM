# Деплой CRM Bot на Railway

## Шаг 1: Подготовка

1. Зарегистрируйся на [railway.app](https://railway.app) (можно через GitHub)
2. Установи Railway CLI:
   ```bash
   npm install -g @railway/cli
   ```
3. Залогинься:
   ```bash
   railway login
   ```

## Шаг 2: Создание проекта

```bash
# Создай новый проект
railway init
```
Выбери "Empty Project"

## Шаг 3: Деплой Backend

```bash
cd "CRM BOT/backend"

# Привяжи к проекту
railway link

# Задеплой
railway up
```

После деплоя скопируй URL бэкенда (например: `https://crm-bot-backend-production.up.railway.app`)

### Настрой переменные окружения для Backend:

В Railway Dashboard → твой проект → Backend service → Variables:

```
TELEGRAM_BOT_TOKEN=8537924648:AAG25YSjHJWLjiEkS0uqBVks513JR6Z_RMs
ADMIN_TELEGRAM_IDS=1470411356
ADMIN_PASSWORD_HASH=demo
GROQ_API_KEY=твой_groq_ключ
CORS_ORIGINS=https://твой-frontend.up.railway.app
DATABASE_URL=sqlite:///./crm.db
SESSION_SECRET=сгенерируй_случайную_строку_32_символа
ENV=production
```

## Шаг 4: Деплой Frontend

```bash
cd "CRM BOT/frontend"

# Создай новый сервис в том же проекте
railway link

# Задеплой
railway up
```

### Настрой переменные окружения для Frontend:

В Railway Dashboard → твой проект → Frontend service → Variables:

```
VITE_API_URL=https://твой-backend.up.railway.app/api
VITE_WS_URL=wss://твой-backend.up.railway.app/ws
```

## Шаг 5: Настройка Webhook для Telegram

После деплоя бэкенда, установи webhook:

```bash
curl "https://api.telegram.org/bot8537924648:AAG25YSjHJWLjiEkS0uqBVks513JR6Z_RMs/setWebhook?url=https://твой-backend.up.railway.app/telegram/webhook"
```

## Шаг 6: Проверка

1. Открой URL фронтенда в браузере
2. Залогинься с паролем `demo`
3. Напиши боту в Telegram - должно появиться в CRM

## Альтернатива: Деплой через GitHub

1. Запушь код в GitHub репозиторий
2. В Railway Dashboard нажми "New Project" → "Deploy from GitHub repo"
3. Выбери репозиторий
4. Railway автоматически определит Dockerfile или создаст билд

## Важно!

- **База данных**: SQLite не сохраняется между редеплоями. Для production лучше добавить PostgreSQL:
  - В Railway Dashboard → Add Service → Database → PostgreSQL
  - Railway автоматически добавит `DATABASE_URL`
  
- **Домен**: Railway даёт бесплатный домен `*.up.railway.app`. Можно подключить свой домен в Settings.

## Команды Railway CLI

```bash
railway status    # Статус проекта
railway logs      # Логи
railway open      # Открыть в браузере
railway variables # Показать переменные
```
