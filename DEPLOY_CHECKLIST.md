# ✅ Чеклист деплоя на сервер

Быстрая шпаргалка для развертывания проекта.

## 📋 Перед началом

- [ ] Есть доступ к серверу по SSH
- [ ] Есть `api_id` и `api_hash` от Telegram
- [ ] Есть номер телефона аккаунта
- [ ] Есть DeepSeek API ключ
- [ ] Есть URL Google таблицы

## 🔧 На сервере

### 1. Установка Docker (если не установлен)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Подготовка директории

```bash
sudo mkdir -p /opt/alpha-parser/app/data
sudo chown -R $USER:$USER /opt/alpha-parser
```

### 3. Клонирование проекта

```bash
cd /opt/alpha-parser
git clone https://github.com/alezzinap1/alpha_parser_pub.git .
```

### 4. Создание `.env` файла

```bash
nano /opt/alpha-parser/app/data/.env
```

**Содержимое:**
```env
ENV_MODE=production
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890
TELEGRAM_PASSWORD=ваш_пароль_или_пусто
DEEPSEEK_API_KEY=ваш_ключ
OPENAI_PROXY=
CSV_URL=ваш_url
```

### 5. Создание `config.json` файла

```bash
cp config.json.example /opt/alpha-parser/app/data/config.json
nano /opt/alpha-parser/app/data/config.json
```

**Замените:**
- `"target_channel": "@your_channel"` → ваш канал
- `"system_prompt": "текст"` → ваш промпт
- `"user_prompt": "текст"` → ваш промпт

### 6. Передача файла сессии (если есть локально)

**На локальном компьютере:**
```powershell
scp userbot2_session.session user@your-server-ip:/opt/alpha-parser/app/data/
```

**На сервере:**
```bash
chmod 600 /opt/alpha-parser/app/data/userbot2_session.session
```

### 7. Первая авторизация (если сессии нет)

```bash
cd /opt/alpha-parser/app
docker-compose build alpha-parser
docker-compose up alpha-parser
```

Когда запросит код:
```bash
echo "12345" > /opt/alpha-parser/app/data/telegram_code.txt
```

После авторизации: Ctrl+C, затем:
```bash
docker-compose up -d
```

### 8. Запуск

```bash
cd /opt/alpha-parser/app
docker-compose up -d
```

### 9. Проверка

```bash
# Статус
docker-compose ps

# Логи
docker-compose logs -f alpha-parser
```

## 📥 Доступ к файлам

**Браузер:** `http://your-server-ip:8080/`

**Скачать БД:**
```bash
curl http://your-server-ip:8080/channels_v2.db -o backup.db
```

## 🔄 Обновление проекта

```bash
cd /opt/alpha-parser/app
git pull
docker-compose build alpha-parser
docker-compose up -d alpha-parser
```

## 📚 Полная инструкция

См. [SERVER_DEPLOYMENT.md](SERVER_DEPLOYMENT.md) для детальной информации.

