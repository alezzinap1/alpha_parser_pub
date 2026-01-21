# Alpha Parser

Telegram бот для парсинга и фильтрации сообщений из каналов.

## Структура проекта

```
alpha-parser/
├── src/                    # Исходный код
│   ├── __init__.py
│   ├── RUN4.py            # Основной файл бота
│   ├── CONFIG.py          # Конфигурация (API ключи, настройки)
│   ├── channel_processors.py  # Процессоры для разных типов каналов
│   ├── exceptions.py      # Кастомные исключения
│   └── config_validator.py # Валидация конфигурации (Pydantic)
├── main.py                # Точка входа для запуска
├── requirements.txt       # Зависимости Python
├── Dockerfile            # Docker образ
├── entrypoint.sh        # Скрипт запуска в Docker
└── README.md           # Документация
```

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте конфигурацию в `src/CONFIG.py`

3. Запустите бота:
```bash
python main.py
```

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
- `CONFIG.py` (переопределения конфигурации)
- `channels_v2.db`
- `userbot2_session.session`

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

