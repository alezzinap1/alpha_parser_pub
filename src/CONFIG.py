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
# Полностью загружаем базовые настройки из переменной окружения,
# чтобы значения (каналы, интервалы, промпты и т.д.) не светились в репозитории.
# Ожидается JSON-строка с полным словарём настроек.
DEFAULT_CONFIGS = json.loads(_require_env("DEFAULT_CONFIG_JSON"))

########################################################################################