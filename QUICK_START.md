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
sudo mkdir -p /opt/alpha-parser/data
sudo chown -R $USER:$USER /opt/alpha-parser
```

### 2. Клонирование проекта

```bash
cd /opt/alpha-parser
git clone https://github.com/alezzinap1/alpha_parser_pub.git .
```

### 3. Создание конфигурации

```bash
nano /opt/alpha-parser/data/.env
```

Заполните файл (см. пример в `CREATE_ENV_FILES.md`):

```env
ENV_MODE=production
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890
TELEGRAM_PASSWORD=your_password
DEEPSEEK_API_KEY=your_key
CSV_URL=your_google_sheets_url
DEFAULT_CONFIG_JSON={"target_channel":"@your_channel",...}
```

### 4. Запуск

```bash
cd /opt/alpha-parser
docker compose up -d
```

### 5. Проверка

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

Для детальной информации см. [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

