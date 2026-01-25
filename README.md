# Alpha Parser

Автономный канал в который пересылаются посты из отслеживаемых телеграмм каналов. Весь контент проходит строгую фильтрацию. Каналы разделены на разные типы.

## Структура проекта

```
alpha-parser/
├── src/                           # Исходный код
│   ├── __init__.py
│   ├── RUN4.py                    # Основной файл бота
│   ├── CONFIG.py                  # Загрузка конфигурации из переменных окружения
│   ├── channel_processors.py      # Процессоры для разных типов каналов
│   ├── config_validator.py        # Валидация конфигурации (Pydantic)
│   └── exceptions.py              # Кастомные исключения
├── .env.test                      # Конфигурация для тестового аккаунта (НЕ в git!)
├── .env.production                # Конфигурация для рабочего аккаунта (НЕ в git!)
├── .env                           # Текущий активный конфиг (создается автоматически)
├── switch_to_test.bat            # Скрипт переключения на тест (Windows)
├── switch_to_test.sh              # Скрипт переключения на тест (Linux/Mac)
├── switch_to_production.bat       # Скрипт переключения на продакшн (Windows)
├── switch_to_production.sh        # Скрипт переключения на продакшн (Linux/Mac)
├── requirements.txt               # Зависимости Python
├── Dockerfile                     # Docker образ
├── entrypoint.sh                  # Скрипт запуска в Docker
├── ACCOUNT_SWITCHING_GUIDE.md     # Подробный гайд по переключению аккаунтов
├── CREATE_ENV_FILES.md            # Инструкция по созданию .env файлов
└── README.md                      # Документация
```

### Файлы данных (создаются автоматически)

**Тестовый режим (`ENV_MODE=test`):**
- `userbot2_test_session.session` - сессия Telegram
- `channels_v2_test.db` - база данных каналов и постов
- `userbot2_test.log` - логи

**Продакшн режим (`ENV_MODE=production`):**
- `userbot2_session.session` - сессия Telegram
- `channels_v2.db` - база данных каналов и постов
- `userbot2.log` - логи

⚠️ **Важно:** Все `.env.*` файлы, сессии, базы данных и логи находятся в `.gitignore` и не коммитятся в git!

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте конфигурацию через переменные окружения:
   - Создайте файлы `.env.test` и `.env.production` (см. `CREATE_ENV_FILES.md`)
   - Все настройки (API ключи, номера телефонов, промпты) хранятся в переменных окружения
   - ⚠️ **Никогда не коммитьте `.env.*` файлы в git!**

3. Переключитесь на нужное окружение:
   - **Windows:** `.\switch_to_test.bat` или `.\switch_to_production.bat`
   - **Linux/Mac:** `./switch_to_test.sh` или `./switch_to_production.sh`

4. Запустите бота:
```bash
python -m src.RUN4
```

## Переключение между тестом и продакшеном

Проект поддерживает работу с двумя разными Telegram аккаунтами:
- **Тестовый аккаунт** — для локального тестирования
- **Рабочий аккаунт** — для продакшн сервера

### Быстрое переключение

**Windows:**
```powershell
# Переключиться на тест
.\switch_to_test.bat

# Переключиться на продакшн
.\switch_to_production.bat
```

**Linux/Mac:**
```bash
# Переключиться на тест
./switch_to_test.sh

# Переключиться на продакшн
./switch_to_production.sh
```

### Что происходит при переключении

1. Скопируется соответствующий `.env.*` файл в `.env`
2. Бот автоматически использует:
   - Отдельную сессию Telegram (`.session` файл)
   - Отдельную базу данных (`.db` файл)
   - Отдельный лог файл (`.log` файл)

Это гарантирует полную изоляцию между тестовым и рабочим окружениями.

### Проверка текущего режима

```powershell
# Windows
Get-Content .env | Select-String "ENV_MODE"

# Linux/Mac
grep ENV_MODE .env
```

### Подробная документация

Для детальной информации см. [ACCOUNT_SWITCHING_GUIDE.md](ACCOUNT_SWITCHING_GUIDE.md)

## Запуск в Docker

### Сборка образа
```bash
docker build -t alpha-parser:latest .
```

### Первый запуск
```bash
docker run -d \
  --name alpha-parser \
  --restart unless-stopped \
  -v /opt/alpha-parser/data:/data \
  alpha-parser:latest
```

Где `/opt/alpha-parser/data` – директория на хосте, где будут храниться:
- `.env` (конфигурация через переменные окружения)
- `channels_v2.db` (или `channels_v2_test.db` для теста)
- `userbot2_session.session` (или `userbot2_test_session.session` для теста)
- `userbot2.log` (или `userbot2_test.log` для теста)

### Переменные окружения для Docker

При запуске в Docker передайте переменные окружения:

```bash
docker run -d \
  --name alpha-parser \
  --restart unless-stopped \
  -v /opt/alpha-parser/data:/data \
  -e TELEGRAM_API_ID="your_api_id" \
  -e TELEGRAM_API_HASH="your_api_hash" \
  -e TELEGRAM_PHONE_NUMBER="+1234567890" \
  -e DEEPSEEK_API_KEY="your_key" \
  -e CSV_URL="your_google_sheets_url" \
  -e ENV_MODE="production" \
  -e DEFAULT_CONFIG_JSON='{"key":"value"}' \
  alpha-parser:latest
```

Или используйте `.env` файл в `/opt/alpha-parser/data/.env`

### Управление контейнером
```bash
docker logs -f alpha-parser      # логи
docker restart alpha-parser      # перезапуск
docker stop alpha-parser         # остановка
docker start alpha-parser        # запуск
```

## Особенности

- ✅ Рефакторинг с соблюдением SOLID принципов
- ✅ Валидация конфигурации через Pydantic
- ✅ Типизация с type hints
- ✅ Кастомные исключения для лучшей обработки ошибок
- ✅ Модульная архитектура с процессорами для разных типов каналов
- ✅ Безопасное хранение конфигурации через переменные окружения
- ✅ Поддержка тестового и продакшн окружений с полной изоляцией
- ✅ Автоматическое переподключение при разрыве соединения
- ✅ Сохранение всех обработанных постов в базу данных
- ✅ Обработка ошибок `AuthKeyDuplicatedError` для работы с несколькими аккаунтами

