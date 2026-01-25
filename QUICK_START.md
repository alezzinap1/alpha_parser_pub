# ⚡ Быстрый старт

Краткая инструкция для быстрого развертывания Alpha Parser на сервере.

## 📋 Предварительные требования

- Сервер с Linux (Ubuntu/Debian)
- Docker и Docker Compose установлены
- SSH доступ к серверу

## 🚀 Установка за 5 минут

### 1. Подготовка сервера

```bash
# Создайте директорию
sudo mkdir -p /opt/alpha-parser/app/data
sudo chown -R $USER:$USER /opt/alpha-parser
```

### 2. Клонирование проекта

```bash
cd /opt/alpha-parser
git clone https://github.com/alezzinap1/alpha_parser_pub.git .
```

### 3. Создание конфигурации

**3.1 Создайте `.env` файл:**

```bash
nano /opt/alpha-parser/app/data/.env
```

Заполните:

```env
ENV_MODE=production
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890
TELEGRAM_PASSWORD=your_password
DEEPSEEK_API_KEY=your_key
OPENAI_PROXY=
CSV_URL=your_google_sheets_url
```

**3.2 Создайте `config.json` файл:**

```bash
cp config.json.example /opt/alpha-parser/app/data/config.json
nano /opt/alpha-parser/app/data/config.json
```

Заполните `target_channel`, `system_prompt` и `user_prompt` реальными значениями.

### 4. Первая авторизация (если сессии нет)

Если у вас нет файла сессии, нужно пройти авторизацию:

```bash
cd /opt/alpha-parser/app
docker-compose build alpha-parser
docker-compose up alpha-parser
```

Когда бот запросит код из SMS, создайте файл:
```bash
echo "12345" > /opt/alpha-parser/app/data/telegram_code.txt
```

После успешной авторизации остановите контейнер (Ctrl+C) и запустите в фоне.

### 5. Запуск

```bash
cd /opt/alpha-parser/app
docker-compose up -d
```

### 6. Проверка

```bash
# Статус
docker compose ps

# Логи
docker compose logs -f alpha-parser
```

## 📥 Доступ к файлам

### Скачать БД и логи:

**Через браузер:**
```
http://your-server-ip:8080/
```

**Через curl:**
```bash
curl http://your-server-ip:8080/channels_v2.db -o backup.db
curl http://your-server-ip:8080/userbot2.log -o backup.log
```

## 📚 Полная документация

- **Детальная инструкция:** [SERVER_DEPLOYMENT.md](SERVER_DEPLOYMENT.md)
- **Полный гайд:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Создание конфигов:** [CREATE_ENV_FILES.md](CREATE_ENV_FILES.md)

