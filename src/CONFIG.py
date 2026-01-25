########################################################################################
"""            ВВОДНЫЕ ДАННЫЕ (через переменные окружения)                     """

import os
import json

try:
    # python-dotenv — опциональная зависимость, для удобства локальной разработки.
    # В проде достаточно выставить переменные окружения.
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover - защитный код
    def load_dotenv(*args, **kwargs):
        return False

def _require_env(name: str) -> str:
    """Возвращает значение переменной окружения или падает с ошибкой, если не задано."""
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Environment variable {name} must be set")
    return value


# Загружаем переменные из .env, если файл существует.
# В проде (Docker/сервер) можно просто задавать переменные окружения без .env.
load_dotenv()

# Критичные параметры авторизации Telegram
api_id = _require_env("TELEGRAM_API_ID")  # номер с сайта
api_hash = _require_env("TELEGRAM_API_HASH")  # тоже с сайта
phone_number = _require_env("TELEGRAM_PHONE_NUMBER")  # телефон зареганного тг акка

# Может быть пустым, если у аккаунта нет 2FA
password_raw = os.getenv("TELEGRAM_PASSWORD")
password = int(password_raw) if password_raw and password_raw.isdigit() else password_raw

# Ключ для DeepSeek/OpenAI-совместимого клиента
deepseek_api_key = _require_env("DEEPSEEK_API_KEY")

# Прокси, если нужно (login:password@ip:port), иначе оставить пустым
openai_proxy = os.getenv("OPENAI_PROXY", "")

# URL Google-таблицы с каналами/настройками (обязательно задаётся извне)
csv_url = _require_env("CSV_URL")

"""
ДОП фишки

Бот обновляет список каналов и настройки из Google-таблицы. 
Настройки задаются в столбцах J (название) и K (значение).
Проверка настроек происходит каждые 2 часа.
Если настройки в таблице некорректны, используются значения по умолчанию.
Бот подписывается на новые каналы из таблицы и парсит их посты.
Есть БД, которая копирует список каналов из таблицы.

Промпты (system_prompt и user_prompt) 
можно менять через Google-таблицу в столбцах J и K.
"""

# === DEFAULT CONFIGS ===
# Загружаем базовые настройки из JSON файла (не из переменной окружения)
# Файл должен находиться в той же директории, что и .env файл
# Для Docker: /data/config.json
# Для локальной разработки: ./config.json или ./data/config.json

def _load_default_configs():
    """Загружает DEFAULT_CONFIGS из JSON файла."""
    # Определяем путь к файлу конфигурации
    # В Docker контейнере используем /data, иначе текущую директорию или ./data
    if os.path.exists('/data'):
        config_path = '/data/config.json'
    elif os.path.exists('./data'):
        config_path = './data/config.json'
    else:
        config_path = './config.json'
    
    if not os.path.exists(config_path):
        raise RuntimeError(
            f"Config file not found: {config_path}\n"
            f"Please create this file with your default configuration.\n"
            f"See config.json.example for template."
        )
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in {config_path}: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {config_path}: {e}")

DEFAULT_CONFIGS = _load_default_configs()

########################################################################################