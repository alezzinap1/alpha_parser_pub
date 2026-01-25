# 🚀 Деплой Alpha Parser на сервер

**Простая пошаговая инструкция для развертывания проекта на сервере.**

## 📋 Что нужно перед началом

1. **Доступ к серверу по SSH**
2. **Данные для Telegram:**
   - `api_id` и `api_hash` (получить на https://my.telegram.org)
   - Номер телефона аккаунта
   - Пароль 2FA (если включен)
3. **DeepSeek API ключ** (получить на https://platform.deepseek.com)
4. **URL Google таблицы** с каналами

---

## 🔧 Шаг 1: Подготовка сервера

### 1.1 Подключитесь к серверу

```bash
ssh user@your-server-ip
```

### 1.2 Установите Docker и Docker Compose (если не установлены)

```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Проверьте установку
docker --version
docker compose version
```

### 1.3 Создайте директорию для проекта

```bash
sudo mkdir -p /opt/alpha-parser/app/data
sudo chown -R $USER:$USER /opt/alpha-parser
```

---

## 📦 Шаг 2: Клонирование проекта

```bash
cd /opt/alpha-parser
git clone https://github.com/alezzinap1/alpha_parser_pub.git .
```

---

## ⚙️ Шаг 3: Создание конфигурации

### 3.1 Создайте файл `.env`

```bash
nano /opt/alpha-parser/app/data/.env
```

### 3.2 Заполните файл следующими данными:

```env
ENV_MODE=production
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890
TELEGRAM_PASSWORD=ваш_пароль_2fa_или_оставьте_пустым
DEEPSEEK_API_KEY=ваш_deepseek_ключ
OPENAI_PROXY=
CSV_URL=ваш_url_google_таблицы
```

**Важно:** 
- Если у аккаунта нет 2FA, оставьте `TELEGRAM_PASSWORD=` пустым
- Если есть прокси для OpenAI, укажите в формате: `login:password@ip:port`

### 3.3 Создайте файл `config.json`

```bash
nano /opt/alpha-parser/app/data/config.json
```

Скопируйте содержимое из `config.json.example` и заполните реальными данными:

```json
{
  "target_channel": "@ваш_канал",
  "table_scan_interval": 120,
  "message_scan_interval": 200,
  "min_length": 95,
  "min_length_wl": 95,
  "blacklist_words": ["addlist"],
  "max_messages_per_channel": 3,
  "channel_type_intervals": {
    "filtered": 1200,
    "whitelist": 300,
    "stats": 120,
    "longcheck": 28800,
    "ranks": 600,
    "whitelist2": 300,
    "type2": 3600
  },
  "btc_eth_threshold": 1000000,
  "other_coin_threshold": 500000,
  "csv_timeout": 30,
  "sleep_between_channels_min": 0.2,
  "sleep_between_channels_max": 0.35,
  "max_null_hash_fixes": 5,
  "log_channel_count_changes_only": true,
  "system_prompt": "ваш_system_prompt",
  "user_prompt": "ваш_user_prompt"
}
```

**Совет:** Используйте `config.json.example` как шаблон, замените только `target_channel`, `system_prompt` и `user_prompt` на реальные значения.

---

## 🚀 Шаг 4: Первая авторизация (создание сессии)

### 4.1 Запустите контейнер для первой авторизации

```bash
cd /opt/alpha-parser/app
docker-compose build alpha-parser
docker-compose up alpha-parser
```

### 4.2 Введите код из SMS

Когда бот запросит код, вы увидите в логах:
```
Telegram code required. Set TELEGRAM_CODE env var or create /data/telegram_code.txt
```

**Вариант 1: Через переменную окружения (рекомендуется)**
```bash
# В другом терминале на сервере
echo "12345" > /opt/alpha-parser/app/data/telegram_code.txt
```

**Вариант 2: Через файл**
```bash
# Создайте файл с кодом
nano /opt/alpha-parser/app/data/telegram_code.txt
# Введите код из SMS
# Сохраните (Ctrl+O, Enter, Ctrl+X)
```

### 4.3 После успешной авторизации

Сессия сохранится в файл `/opt/alpha-parser/app/data/userbot2_session.session`. 
Остановите контейнер (Ctrl+C) и запустите в фоне:

```bash
docker-compose up -d alpha-parser
```

---

## 📥 Шаг 5: Передача файла сессии с локального компьютера (если есть)

Если у вас уже есть файл сессии на локальном компьютере:

### 5.1 На локальном компьютере (Windows PowerShell)

```powershell
# Найдите файл сессии
# Обычно он называется: userbot2_session.session или userbot2_test_session.session

# Скопируйте на сервер через scp
scp userbot2_session.session user@your-server-ip:/opt/alpha-parser/app/data/
```

### 5.2 На сервере проверьте права доступа

```bash
chmod 600 /opt/alpha-parser/app/data/userbot2_session.session
chown $USER:$USER /opt/alpha-parser/app/data/userbot2_session.session
```

---

## ✅ Шаг 6: Запуск проекта

```bash
cd /opt/alpha-parser/app
docker-compose up -d
```

### Проверка статуса

```bash
# Статус контейнеров
docker-compose ps

# Логи бота
docker-compose logs -f alpha-parser
```

Если все работает, вы увидите:
```
OK, user: ваш_username
Бот запущен!
```

---

## 📊 Шаг 7: Доступ к файлам (логи и БД)

### Через браузер

Откройте в браузере:
```
http://your-server-ip:8080/
```

Вы увидите список файлов:
- `channels_v2.db` - база данных
- `userbot2.log` - логи
- Другие файлы

### Через curl (скачать файл)

```bash
# Скачать БД
curl http://your-server-ip:8080/channels_v2.db -o backup.db

# Скачать логи
curl http://your-server-ip:8080/userbot2.log -o backup.log
```

---

## 🔄 Управление проектом

### Просмотр логов

```bash
# Все логи
docker-compose logs -f alpha-parser

# Последние 50 строк
docker-compose logs --tail=50 alpha-parser
```

### Перезапуск

```bash
docker-compose restart alpha-parser
```

### Остановка

```bash
docker-compose down
```

### Обновление проекта

```bash
cd /opt/alpha-parser/app
git pull
docker-compose build alpha-parser
docker-compose up -d alpha-parser
```

---

## 🐛 Решение проблем

### Проблема: Контейнер не запускается

```bash
# Проверьте логи
docker-compose logs alpha-parser

# Проверьте, что файлы существуют
ls -la /opt/alpha-parser/app/data/.env
ls -la /opt/alpha-parser/app/data/config.json
```

### Проблема: Ошибка авторизации

1. Убедитесь, что файл сессии существует:
   ```bash
   ls -la /opt/alpha-parser/app/data/userbot2_session.session
   ```

2. Если файла нет, удалите его и пройдите авторизацию заново:
   ```bash
   rm /opt/alpha-parser/app/data/userbot2_session.session
   docker-compose restart alpha-parser
   ```

### Проблема: JSON ошибка в config.json

```bash
# Проверьте валидность JSON
python3 -c "import json; json.load(open('/opt/alpha-parser/app/data/config.json'))"
```

### Проблема: Не могу скачать файлы через HTTP

1. Проверьте, что файл-сервер запущен:
   ```bash
   docker-compose ps file-server
   ```

2. Проверьте порт 8080:
   ```bash
   netstat -tuln | grep 8080
   ```

3. Проверьте firewall:
   ```bash
   sudo ufw allow 8080/tcp
   ```

---

## 📝 Важные файлы

**На сервере в `/opt/alpha-parser/app/data/`:**
- `.env` - конфигурация (секретный файл!)
- `config.json` - настройки бота (секретный файл!)
- `userbot2_session.session` - сессия Telegram (секретный файл!)
- `channels_v2.db` - база данных (доступна через HTTP)
- `userbot2.log` - логи (доступны через HTTP)

**⚠️ ВАЖНО:** Файлы `.env`, `config.json` и `*.session` НЕ доступны через HTTP файл-сервер для безопасности!

---

## 🔐 Безопасность

1. **Никогда не коммитьте** `.env`, `config.json` и `*.session` файлы в git
2. **Ограничьте доступ** к директории `/opt/alpha-parser/app/data/`:
   ```bash
   chmod 700 /opt/alpha-parser/app/data
   ```
3. **Используйте firewall** для ограничения доступа к порту 8080 только с вашего IP

---

## 📞 Дополнительная помощь

- **Полный гайд:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Быстрый старт:** [QUICK_START.md](QUICK_START.md)
- **Создание .env:** [CREATE_ENV_FILES.md](CREATE_ENV_FILES.md)

