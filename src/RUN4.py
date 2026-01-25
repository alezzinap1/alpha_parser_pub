import csv
import requests
from io import StringIO
import sqlite3
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.types import InputPeerNotifySettings, InputPeerChannel
import logging
import asyncio
from openai import OpenAI
import random
import re
import time
import traceback
from telethon.errors import PhoneMigrateError, FloodWaitError, SessionPasswordNeededError
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError
import ast
from typing import Dict, List, Tuple, Optional, Any, Set, Union
from contextlib import contextmanager
from datetime import datetime
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

# === PATH CONFIGURATION ===
# Определяем базовый путь для данных (Docker или локально) - ДО импорта CONFIG
import os
DATA_DIR = '/data' if os.path.exists('/data') else '.'
# Загружаем .env для определения режима (до импорта CONFIG)
from dotenv import load_dotenv  # type: ignore
load_dotenv()
ENV_MODE = os.getenv('ENV_MODE', 'production').lower()
# Используем разные сессии для теста и продакшна, чтобы избежать конфликтов
SESSION_NAME = os.getenv('SESSION_NAME', 
    'userbot2_test_session' if ENV_MODE == 'test' else 'userbot2_session')
DB_FILE = os.getenv('DB_FILE', 
    os.path.join(DATA_DIR, "channels_v2_test.db" if ENV_MODE == 'test' else "channels_v2.db") 
    if DATA_DIR != '.' else ("channels_v2_test.db" if ENV_MODE == 'test' else "channels_v2.db"))
SESSION_PATH = os.getenv('SESSION_PATH', 
    os.path.join(DATA_DIR, SESSION_NAME) if DATA_DIR != '.' else SESSION_NAME)
LOG_FILE = os.getenv('LOG_FILE', 
    os.path.join(DATA_DIR, "userbot2_test.log" if ENV_MODE == 'test' else "userbot2.log") 
    if DATA_DIR != '.' else ("userbot2_test.log" if ENV_MODE == 'test' else "userbot2.log"))

# === CONFIG ===
from .CONFIG import (
    api_id, api_hash, phone_number, password, deepseek_api_key, csv_url, DEFAULT_CONFIGS
)

# === CHANNEL PROCESSORS ===
from .channel_processors import (
    CHANNEL_TYPE_FILTERED, CHANNEL_TYPE_WHITELIST, CHANNEL_TYPE_STATS, CHANNEL_TYPE_LONGCHECK,
    CHANNEL_TYPE_RANKS, CHANNEL_TYPE_WHITELIST2, CHANNEL_TYPE_TYPE2,
    MESSAGE_PROCESSORS, parse_amount
)

# === CONFIG VALIDATOR ===
from .config_validator import validate_and_update_config

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# === OPENAI / DEEPSEEK ===
openai_client = OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com")

# Проверка критических параметров при импорте
if not api_id or not api_hash:
    raise ValueError("api_id and api_hash must be set in CONFIG.py")
if not phone_number:
    raise ValueError("phone_number must be set in CONFIG.py")
if not deepseek_api_key:
    raise ValueError("deepseek_api_key must be set in CONFIG.py")

# === TELETHON ===
# Передаем phone при создании клиента, чтобы избежать интерактивного запроса в Docker
client = TelegramClient(
    SESSION_PATH,
    api_id,
    api_hash,
    connection_retries=5,
    phone=phone_number  # Добавляем phone, чтобы избежать input() в Docker
)

# === CONSTANTS ===
MUTE_UNTIL_FOREVER = 2**31 - 1
CONFIG_CHECK_INTERVAL = 7200  # 2 часа
MAX_NULL_HASH_FIXES = 5
SLEEP_AFTER_JOIN_MIN = 25
SLEEP_AFTER_JOIN_MAX = 40
SLEEP_AFTER_FLOOD_MIN = 13
SLEEP_AFTER_FLOOD_MAX = 90
SLEEP_BETWEEN_MESSAGES_MIN = 0.1
SLEEP_BETWEEN_MESSAGES_MAX = 0.2
SLEEP_AFTER_FLOOD_SHORT_MIN = 0.2
SLEEP_AFTER_FLOOD_SHORT_MAX = 0.6

# Глобальные конфигурации
CONFIG = DEFAULT_CONFIGS.copy()
CONFIG['table_scan_interval'] = max(60, int(CONFIG['table_scan_interval']))
CONFIG['message_scan_interval'] = max(30, int(CONFIG['message_scan_interval']))

# === CONFIG KEYS ===
ALLOWED_CONFIG_KEYS = list(DEFAULT_CONFIGS.keys())

# Кэш для отслеживания количества каналов (для уменьшения логирования)
_channel_count_cache: Dict[int, int] = {}

# === HELPER FUNCTIONS ===
@contextmanager
def get_db_connection():
    """Context manager для работы с БД - автоматически закрывает соединение"""
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

async def safe_forward_message(
    message_id: int,
    peer: InputPeerChannel,
    ch_link: str,
    channel_type: int,
    counters: dict,
    log_prefix: str = "",
    use_short_delay: bool = True
) -> bool:
    """
    Безопасная пересылка сообщения с обработкой ошибок Telegram.
    Возвращает True если успешно, False если ошибка.
    """
    try:
        await ensure_connected()  # Проверка перед отправкой
        await asyncio.sleep(random.uniform(SLEEP_BETWEEN_MESSAGES_MIN, SLEEP_BETWEEN_MESSAGES_MAX))
        await client.forward_messages(CONFIG['target_channel'], message_id, from_peer=peer)
        log_msg = log_prefix if log_prefix else f"https://t.me/{ch_link}/{message_id} (Type {channel_type}): FW → {CONFIG['target_channel']}: {message_id}"
        logging.info(log_msg)
        counters['forwarded'] += 1
        return True
    except ConnectionError as e:
        logging.warning(f"Connection lost during forward: {e}, reconnecting...")
        try:
            await ensure_connected()
        except Exception as reconnect_error:
            logging.error(f"Reconnection failed: {reconnect_error}")
        counters['skipped'] += 1
        return False
    except FloodWaitError as e:
        logging.warning(f"https://t.me/{ch_link}/{message_id}: FloodWait {e.seconds}s")
        delay_min = SLEEP_AFTER_FLOOD_SHORT_MIN if use_short_delay else SLEEP_AFTER_FLOOD_MIN
        delay_max = SLEEP_AFTER_FLOOD_SHORT_MAX if use_short_delay else SLEEP_AFTER_FLOOD_MAX
        await asyncio.sleep(e.seconds + random.uniform(delay_min, delay_max))
        counters['skipped'] += 1
        return False
    except errors.rpcerrorlist.MsgIdInvalidError as e:
        logging.warning(f"Ignored invalid message ID: https://t.me/{ch_link}/{message_id}, error: {e}")
        counters['skipped'] += 1
        return False
    except (errors.RPCError, ConnectionError) as e:
        logging.error(f"RPC error forwarding message: {e}")
        counters['skipped'] += 1
        return False

async def join_and_mute_channel(
    channel_username: str,
    stats: Set[str],
    whitelist: Set[str],
    longcheck: Set[str],
    ranks: Set[str],
    whitelist2: Set[str],
    type2: Set[str]
) -> Optional[Tuple[int, int, int, int]]:
    """
    Подписывается на канал и отключает уведомления.
    Возвращает (chat_id, access_hash, last_message_id, channel_type) или None при ошибке.
    """
    try:
        logging.info(f"Join: {channel_username}")
        result = await client(JoinChannelRequest(channel_username))
        await asyncio.sleep(random.uniform(SLEEP_AFTER_JOIN_MIN, SLEEP_AFTER_JOIN_MAX))
        chat = result.chats[0]
        await client(UpdateNotifySettingsRequest(
            peer=InputPeerChannel(chat.id, chat.access_hash),
            settings=InputPeerNotifySettings(mute_until=MUTE_UNTIL_FOREVER)
        ))
        last_msg = await client.get_messages(InputPeerChannel(chat.id, chat.access_hash), limit=1)
        last_id = last_msg[0].id if last_msg else 0
        ctype = _get_channel_type(channel_username, stats, whitelist, longcheck, ranks, whitelist2, type2)
        return chat.id, chat.access_hash, last_id, ctype
    except FloodWaitError as e:
        logging.warning(f"FloodWait {e.seconds}s join {channel_username}")
        await asyncio.sleep(e.seconds + random.uniform(SLEEP_AFTER_FLOOD_MIN, SLEEP_AFTER_FLOOD_MAX))
        return None
    except (errors.RPCError, ConnectionError, ValueError) as e:
        logging.error(f"Ошибка подписки {channel_username}: {e}")
        return None

def setup_database() -> None:
    """Инициализирует базу данных"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            chat_id INTEGER,
            last_message_id INTEGER DEFAULT 0,
            channel_type INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertisements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE,
            channel_username TEXT
        )
    """)
    # Таблица для хранения всех обработанных постов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            channel_type INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            post_url TEXT NOT NULL,
            text TEXT,
            text_length INTEGER DEFAULT 0,
            published_at TIMESTAMP,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_advertisement BOOLEAN DEFAULT 0,
            is_forwarded BOOLEAN DEFAULT 0,
            has_media BOOLEAN DEFAULT 0,
            blacklisted BOOLEAN DEFAULT 0,
            UNIQUE(channel, message_id)
        )
    """)
    # Оптимизированные индексы для быстрого поиска
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_channel ON posts(channel)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_published_at ON posts(published_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_is_advertisement ON posts(is_advertisement)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_is_forwarded ON posts(is_forwarded)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_channel_type ON posts(channel_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_channel_message_id ON posts(channel, message_id)")
    cur.execute("PRAGMA table_info(channels)")
    columns = [col[1] for col in cur.fetchall()]
    if 'access_hash' not in columns:
        cur.execute("ALTER TABLE channels ADD COLUMN access_hash INTEGER")
        logging.info("Добавлен столбец access_hash в таблицу channels")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_channels_username ON channels (username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_advertisements_message_id ON advertisements (message_id)")
    conn.commit()
    conn.close()
    logging.info("Database initialized with posts table")

def get_tracked_channels() -> List[Tuple[str, int, int, int, Optional[int]]]:
    """Получает список отслеживаемых каналов из БД"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, last_message_id, channel_type, chat_id, access_hash FROM channels")
        return cur.fetchall()

def add_channel_to_db(
    username: str,
    chat_id: int,
    access_hash: Optional[int],
    last_message_id: int = 0,
    channel_type: int = 0
) -> None:
    """Добавляет канал в БД"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO channels (username, chat_id, access_hash, last_message_id, channel_type)
            VALUES (?, ?, ?, ?, ?)
        """, (username, chat_id, access_hash, last_message_id, channel_type))

def update_last_message_id(channel_username: str, message_id: int) -> None:
    """Обновляет last_message_id для канала"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE channels SET last_message_id = ? WHERE username = ?", (message_id, channel_username))

def update_channel_type(channel_username: str, channel_type: int) -> None:
    """Обновляет тип канала"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE channels SET channel_type = ? WHERE username = ?", (channel_type, channel_username))

def is_advertisement_post(message_id: int) -> bool:
    """Проверяет, помечено ли сообщение как реклама"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM advertisements WHERE message_id = ?", (message_id,))
        res = cur.fetchone()
        return res is not None

def add_advertisement_post(message_id: int, channel_username: str) -> None:
    """Добавляет сообщение в список рекламы"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO advertisements (message_id, channel_username) VALUES (?, ?)",
            (message_id, channel_username)
        )

def save_posts_batch(posts: List[Dict[str, Any]]) -> None:
    """
    Оптимизированное батч-сохранение постов в БД.
    
    Args:
        posts: Список словарей с данными постов. Каждый словарь должен содержать:
            - channel: str
            - channel_type: int
            - message_id: int
            - post_url: str
            - text: Optional[str]
            - published_at: Optional[datetime]
            - is_advertisement: bool
            - is_forwarded: bool
            - has_media: bool
            - blacklisted: bool
    """
    if not posts:
        return
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        # Подготавливаем данные для батч-вставки
        batch_data = []
        for post in posts:
            published_at = post.get('published_at')
            # Конвертируем datetime в строку ISO format для SQLite
            if published_at:
                if isinstance(published_at, datetime):
                    published_at_str = published_at.isoformat()
                elif isinstance(published_at, str):
                    published_at_str = published_at
                else:
                    published_at_str = None
            else:
                published_at_str = None
            
            batch_data.append((
                post['channel'],
                post['channel_type'],
                post['message_id'],
                post['post_url'],
                post.get('text'),
                post.get('text_length', 0),
                published_at_str,
                int(post.get('is_advertisement', False)),
                int(post.get('is_forwarded', False)),
                int(post.get('has_media', False)),
                int(post.get('blacklisted', False))
            ))
        
        # Используем executemany для батч-вставки
        cur.executemany("""
            INSERT OR REPLACE INTO posts 
            (channel, channel_type, message_id, post_url, text, text_length, 
             published_at, is_advertisement, is_forwarded, has_media, blacklisted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch_data)
        if len(posts) > 0:
            logging.info(f"Saved batch of {len(posts)} posts to database")

def update_post_forwarded(channel: str, message_id: int, is_forwarded: bool = True) -> None:
    """
    Обновляет статус пересылки поста.
    
    Args:
        channel: Название канала
        message_id: ID сообщения
        is_forwarded: Был ли пост переслан
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE posts SET is_forwarded = ? WHERE channel = ? AND message_id = ?",
            (int(is_forwarded), channel, message_id)
        )

async def is_blacklisted(text: str) -> bool:
    """Проверяет, содержит ли текст слова из blacklist"""
    if not text or not isinstance(text, str):
        return False
    tl = text.lower()
    for w in CONFIG['blacklist_words']:
        if w.lower() in tl:
            logging.info(f"Blacklisted word: {w}")
            return True
    return False

async def is_advertisement(text: str) -> bool:
    """Проверяет, является ли текст рекламой через AI"""
    try:
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
        text = re.sub(r'[^\w\s.,!?а-яА-Я$]', '', text)
        if not text.strip():
            logging.warning("Текст пуст после очистки, скип")
            return False
        resp = openai_client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": CONFIG['system_prompt']},
                {
                    "role": "user",
                    "content": CONFIG['user_prompt'].format(text=text)
                }
            ],
            max_tokens=10,
            temperature=1
        )
        result = resp.choices[0].message.content.strip().lower()
        logging.info(f"Классификатор: {result}")
        return result == "нет"
    except Exception as e:
        logging.error(f"Ошибка OpenAI при анализе текста: {e}\n{traceback.format_exc()}")
        return False  # При ошибке не считаем рекламой (безопасное поведение)

def _get_channel_type(
    ch: str,
    stats: Set[str],
    whitelist: Set[str],
    longcheck: Set[str],
    ranks: Set[str],
    whitelist2: Set[str],
    type2: Set[str]
) -> int:
    """Определяет тип канала по его принадлежности к множествам."""
    if ch in stats:
        return CHANNEL_TYPE_STATS
    elif ch in whitelist:
        return CHANNEL_TYPE_WHITELIST
    elif ch in longcheck:
        return CHANNEL_TYPE_LONGCHECK
    elif ch in ranks:
        return CHANNEL_TYPE_RANKS
    elif ch in whitelist2:
        return CHANNEL_TYPE_WHITELIST2
    elif ch in type2:
        return CHANNEL_TYPE_TYPE2
    else:
        return CHANNEL_TYPE_FILTERED

async def process_channel(
    channel: str,
    last_message_id: int,
    channel_type: int,
    chat_id: int,
    access_hash: Optional[int]
) -> dict:
    """Обрабатывает канал, используя соответствующий процессор"""
    ch_link = channel.lstrip('@')
    counters = {'fetched': 0, 'forwarded': 0, 'skipped': 0, 'ads': 0}
    
    try:
        # Проверяем соединение перед обработкой
        await ensure_connected()
        
        peer = InputPeerChannel(chat_id, access_hash)
        lim = max(1, int(CONFIG['max_messages_per_channel']) 
                 if str(CONFIG['max_messages_per_channel']).isdigit() else 100)
        
        messages = await client.get_messages(peer, min_id=last_message_id, limit=lim)
        counters['fetched'] = len(messages)
        
        if not messages:
            return counters
        
        messages = sorted(messages, key=lambda m: m.id)
        max_id = last_message_id
        
        # Получаем процессор для этого типа канала
        processor = MESSAGE_PROCESSORS.get(channel_type)
        if not processor:
            logging.warning(f"Неизвестный тип канала: {channel_type}, пропускаем")
            return counters
        
        # Список для батч-сохранения постов
        posts_batch = []
        
        # Обрабатываем каждое сообщение
        for message in messages:
            if message.id <= last_message_id:
                continue
            
            max_id = max(max_id, message.id)
            
            # Пропускаем служебные сообщения
            if message.action:
                logging.info(f"Skipped service message: https://t.me/{ch_link}/{message.id}")
                continue
            
            # Вызываем процессор с нужными параметрами
            await processor(
                message, peer, ch_link, channel_type, counters,
                safe_forward_message, is_blacklisted, is_advertisement,
                is_advertisement_post, add_advertisement_post,
                config=CONFIG, channel=channel,
                posts_batch=posts_batch  # Передаем список для сбора постов
            )
        
        # Сохраняем все посты батчем в БД
        if posts_batch:
            try:
                save_posts_batch(posts_batch)
            except Exception as e:
                logging.error(f"Error saving posts batch for {channel}: {e}\n{traceback.format_exc()}")
        
        # Обновляем last_message_id
        if max_id > last_message_id:
            update_last_message_id(channel, max_id)
        
        return counters
        
    except AuthKeyDuplicatedError as e:
        logging.error(
            f"@{channel}: AuthKeyDuplicatedError - сессия используется с двух IP одновременно!\n"
            f"Останови бота на сервере или используй другой аккаунт для локального тестирования.\n"
            f"Текущая сессия: {SESSION_PATH}\n"
            f"Проверь, что локально используется тестовый аккаунт (ENV_MODE=test)"
        )
        # Пропускаем этот канал, но не падаем полностью
        return counters
    except ConnectionError as e:
        logging.warning(f"@{channel}: Connection lost, attempting reconnect...")
        try:
            await ensure_connected()
            return counters
        except Exception as reconnect_error:
            logging.error(f"@{channel}: Reconnection failed: {reconnect_error}")
            return counters
    except Exception as e:
        logging.error(f"@{channel} (Type {channel_type}): Ошибка: {e}\n{traceback.format_exc()}")
        return counters

async def remove_channel(channel_username, chat_id, access_hash):
    try:
        peer = InputPeerChannel(chat_id, access_hash)
        await client(LeaveChannelRequest(peer))
        logging.info(f"Left: {channel_username}")
    except FloodWaitError as e:
        logging.warning(f"FloodWait {e.seconds}s leave {channel_username}")
        await asyncio.sleep(e.seconds + random.uniform(SLEEP_AFTER_FLOOD_MIN, SLEEP_AFTER_FLOOD_MAX))
    except Exception as e:
        logging.error(f"Ошибка отписки {channel_username}: {e}")
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM channels WHERE username = ?", (channel_username,))
    logging.info(f"Удалён из БД: {channel_username}")

def _parse_channel_from_row(row: List[str], index: int, channel_set: Set[str]) -> None:
    """Парсит канал из строки CSV и добавляет в множество"""
    if len(row) > index and row[index].strip():
        ch = row[index].strip()
        channel_set.add('@' + ch if not ch.startswith('@') else ch)

def load_csv():
    try:
        timeout = CONFIG.get('csv_timeout', 30)
        resp = requests.get(csv_url, timeout=timeout)
        resp.raise_for_status()
        csv_content = StringIO(resp.text)
        reader = csv.reader(csv_content, delimiter=',')
        next(reader, None)  # skip header
        rows = list(reader)
        logging.info(f"Загружено {len(rows)} строк из CSV")
        return rows
    except Exception as e:
        logging.error(f"Ошибка загрузки CSV: {e}\n{traceback.format_exc()}")
        return []

async def fetch_channels(csv_rows: List[List[str]]) -> None:
    """Обрабатывает каналы из CSV"""
    if not csv_rows:
        return
    try:
        filtered: Set[str] = set()
        whitelist: Set[str] = set()
        stats: Set[str] = set()
        longcheck: Set[str] = set()
        ranks: Set[str] = set()
        whitelist2: Set[str] = set()
        type2: Set[str] = set()
        
        for row in csv_rows:
            if not row:
                continue
            _parse_channel_from_row(row, 0, filtered)
            _parse_channel_from_row(row, 1, whitelist)
            _parse_channel_from_row(row, 2, stats)
            _parse_channel_from_row(row, 3, longcheck)
            _parse_channel_from_row(row, 4, ranks)
            _parse_channel_from_row(row, 5, whitelist2)
            _parse_channel_from_row(row, 6, type2)

        all_google = stats | whitelist | longcheck | filtered | ranks | whitelist2 | type2
        db_channels = {c[0] for c in get_tracked_channels()}

        new_channels = all_google - db_channels
        removed = db_channels - all_google
        existing = all_google & db_channels

        for ch in new_channels:
            try:
                result = await join_and_mute_channel(ch, stats, whitelist, longcheck, ranks, whitelist2, type2)
                if result:
                    chat_id, access_hash, last_id, ctype = result
                    add_channel_to_db(ch, chat_id, access_hash, last_id, ctype)
                    logging.info(f"Joined and muted: {ch}, type={ctype}")
            except Exception as e:
                logging.error(f"Ошибка подписки на канал {ch}: {e}")

        max_fixes = CONFIG.get('max_null_hash_fixes', MAX_NULL_HASH_FIXES)
        existing_with_null = [
            (ch, _get_channel_type(ch, stats, whitelist, longcheck, ranks, whitelist2, type2))
            for ch in existing
            if next((c[4] for c in get_tracked_channels() if c[0] == ch), None) is None
        ][:max_fixes]
        for ch, ctype in existing_with_null:
            logging.info(f"Канал {ch} имеет NULL access_hash, удаляем и переподписываемся")
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM channels WHERE username = ?", (ch,))
            try:
                result = await join_and_mute_channel(ch, stats, whitelist, longcheck, ranks, whitelist2, type2)
                if result:
                    chat_id, access_hash, last_id, ctype = result
                    add_channel_to_db(ch, chat_id, access_hash, last_id, ctype)
                    logging.info(f"Переподписан: {ch}, type={ctype}")
            except Exception as e:
                logging.error(f"Ошибка переподписки на канал {ch}: {e}")

        for ch in existing:
            ctype = _get_channel_type(ch, stats, whitelist, longcheck, ranks, whitelist2, type2)
            update_channel_type(ch, ctype)

        for ch in removed:
            row = next((c for c in get_tracked_channels() if c[0] == ch), None)
            if row:
                try:
                    await remove_channel(ch, row[3], row[4])
                except Exception as e:
                    logging.error(f"Ошибка удаления {ch}: {e}")

    except Exception as e:
        logging.error(f"Ошибка обработки каналов из CSV: {e}\n{traceback.format_exc()}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при обработке каналов: {e}\n{traceback.format_exc()}")

async def update_configs(csv_rows: List[List[str]]) -> None:
    """Обновляет конфигурацию из CSV"""
    logging.info("Проверка настроек...")
    if not csv_rows:
        logging.warning("CSV пуст, используются настройки по умолчанию")
        return
    
    # Парсинг конфигов из CSV
    configs: Dict[str, Any] = {}
    for row in csv_rows:
        if len(row) > 9 and row[9].strip():
            key = row[9].strip()
            value = row[10].strip() if len(row) > 10 else ''
            if key in ALLOWED_CONFIG_KEYS:
                if key in ['system_prompt', 'user_prompt']:
                    try:
                        value = value.encode('latin1').decode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError) as e:
                        logging.warning(f"Ошибка декодирования {key}: {e}, используется как есть")
                configs[key] = value
    
    # Простая валидация и обновление
    try:
        updated_config = validate_and_update_config(CONFIG, configs)
        if updated_config != CONFIG:
            CONFIG.update(updated_config)
            logging.info(f"Новые настройки применены: {list(configs.keys())}")
    except Exception as e:
        logging.warning(f"Ошибка валидации конфигурации: {e}, используются текущие значения")

async def _process_channel_batch(
    batch: List[Tuple[str, int, int, Optional[int]]],
    channel_type: int,
    sleep_min: float,
    sleep_max: float
) -> dict:
    """Обрабатывает батч каналов"""
    total_counters = {'fetched': 0, 'forwarded': 0, 'skipped': 0, 'ads': 0}
    for channel, last_message_id, chat_id, access_hash in batch:
        counters = await process_channel(channel, last_message_id, channel_type, chat_id, access_hash)
        for k in total_counters:
            total_counters[k] += counters[k]
        await asyncio.sleep(random.uniform(sleep_min, sleep_max))
    return total_counters

async def fetch_unread_messages(
    channels: List[Tuple[str, int, int, int, Optional[int]]],
    channel_type: int
) -> None:
    type_channels = [(ch[0], ch[1], ch[3], ch[4]) for ch in channels if ch[2] == channel_type]
    count = len(type_channels)
    
    # Логируем только если количество изменилось или отключен режим "только при изменении"
    log_changes_only = CONFIG.get('log_channel_count_changes_only', True)
    if not log_changes_only or _channel_count_cache.get(channel_type) != count:
        logging.info(f"Каналов типа {channel_type}: {count}")
        _channel_count_cache[channel_type] = count
    
    sleep_min = CONFIG.get('sleep_between_channels_min', 0.2)
    sleep_max = CONFIG.get('sleep_between_channels_max', 0.35)
    batch_size = 40 if channel_type in (CHANNEL_TYPE_FILTERED, CHANNEL_TYPE_LONGCHECK) else 0
    
    if batch_size > 0:
        total_counters = {'fetched': 0, 'forwarded': 0, 'skipped': 0, 'ads': 0}
        for i in range(0, len(type_channels), batch_size):
            batch = type_channels[i:i + batch_size]
            start_idx = i + 1
            end_idx = min(i + batch_size, len(type_channels))
            logging.info(f"Обработка каналов {start_idx}-{end_idx}")
            batch_counters = await _process_channel_batch(batch, channel_type, sleep_min, sleep_max)
            for k in total_counters:
                total_counters[k] += batch_counters[k]
    else:
        total_counters = await _process_channel_batch(type_channels, channel_type, sleep_min, sleep_max)

def _normalize_intervals(d: Dict[str, Any]) -> Dict[int, int]:
    """Нормализует интервалы для типов каналов"""
    name2id = {
        'filtered': CHANNEL_TYPE_FILTERED,
        'whitelist': CHANNEL_TYPE_WHITELIST,
        'stats': CHANNEL_TYPE_STATS,
        'longcheck': CHANNEL_TYPE_LONGCHECK,
        'ranks': CHANNEL_TYPE_RANKS,
        'whitelist2': CHANNEL_TYPE_WHITELIST2,
        'type2': CHANNEL_TYPE_TYPE2,
        '0': CHANNEL_TYPE_FILTERED,
        '1': CHANNEL_TYPE_WHITELIST,
        '2': CHANNEL_TYPE_STATS,
        '3': CHANNEL_TYPE_LONGCHECK,
        '4': CHANNEL_TYPE_RANKS,
        '5': CHANNEL_TYPE_WHITELIST2,
        '6': CHANNEL_TYPE_TYPE2,
    }
    defaults = {
        CHANNEL_TYPE_FILTERED: 900,
        CHANNEL_TYPE_WHITELIST: 60,
        CHANNEL_TYPE_STATS: 30,
        CHANNEL_TYPE_LONGCHECK: 43200,
        CHANNEL_TYPE_RANKS: 600,
        CHANNEL_TYPE_WHITELIST2: 300,
        CHANNEL_TYPE_TYPE2: 3600
    }
    
    out = {}
    for k, v in d.items():
        kk = k
        if isinstance(kk, str):
            kk = name2id.get(kk.strip().lower())
        if kk is not None:
            try:
                iv = int(v)
                out[kk] = max(60, iv) if kk != CHANNEL_TYPE_STATS else max(30, iv)
            except (ValueError, TypeError):
                continue
    
    # Добавляем дефолты для отсутствующих типов
    for k, v in defaults.items():
        if k not in out:
            out[k] = v
    
    return out

async def _start_client():
    """Единая точка авторизации клиента"""
    # Проверка phone_number
    if not phone_number:
        raise ValueError("phone_number not configured in CONFIG.py")
    
    # Если сессия существует, код не нужен
    session_file = f"{SESSION_PATH}.session"
    if os.path.exists(session_file):
        # Пытаемся подключиться без кода
        try:
            return await client.start(phone=phone_number, password=password)
        except Exception as e:
            logging.warning(f"Failed to start with existing session: {e}, will request code")
            # Если не получилось, запрашиваем код
    
    # Если сессии нет, используем код из файла или переменной окружения
    code_file = os.path.join(DATA_DIR, 'telegram_code.txt')
    code_env = os.environ.get('TELEGRAM_CODE')
    
    def get_code():
        if code_env:
            logging.info("Using code from TELEGRAM_CODE environment variable")
            return code_env
        if os.path.exists(code_file):
            logging.info(f"Reading code from {code_file}")
            with open(code_file, 'r') as f:
                code = f.read().strip()
            os.remove(code_file)
            return code
        raise ValueError(
            f"Telegram code required. Set TELEGRAM_CODE env var or create {code_file}"
        )
    
    return await client.start(
        phone=phone_number,
        code_callback=get_code,
        password=password
    )

async def ensure_connected():
    """Проверяет соединение и переподключается при необходимости"""
    if not client.is_connected():
        logging.warning("Client disconnected, reconnecting...")
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logging.warning("Session expired, re-authenticating...")
                await _start_client()
            else:
                logging.info("Reconnected successfully")
        except AuthKeyDuplicatedError as e:
            logging.error(
                f"❌ Reconnection failed: AuthKeyDuplicatedError!\n"
                f"Сессия используется с двух IP одновременно.\n"
                f"Останови бота на сервере или используй другой аккаунт для локального тестирования."
            )
            raise
        except Exception as e:
            logging.error(f"Reconnection failed: {e}")
            await asyncio.sleep(5)
            raise
    return True

async def main():
    # Проверка критических параметров перед запуском
    if not CONFIG.get('target_channel'):
        raise ValueError("target_channel must be set in CONFIG")
    
    logging.info(f"Data directory: {DATA_DIR}")
    logging.info(f"Session path: {SESSION_PATH}")
    logging.info(f"Database file: {DB_FILE}")
    
    # Проверка соответствия режима и сессии
    env_mode = os.getenv('ENV_MODE', 'production').lower()
    if env_mode == 'test':
        if 'test' not in SESSION_NAME:
            logging.warning(
                f"⚠ WARNING: ENV_MODE=test, but session name is '{SESSION_NAME}' (should contain 'test').\n"
                f"Убедись, что используешь тестовый аккаунт для локального тестирования!"
            )
    else:
        if 'test' in SESSION_NAME:
            logging.warning(
                f"⚠ WARNING: ENV_MODE=production, but session name is '{SESSION_NAME}' (contains 'test').\n"
                f"Убедись, что используешь правильный режим!"
            )
    
    setup_database()
    try:
        logging.info("Авторизация…")
        target_peer = await client.get_input_entity(CONFIG['target_channel'])
        logging.info(f"Target channel resolved: {CONFIG['target_channel']}")
        await _start_client()
        user = await client.get_me()
        logging.info(f"OK, user: {user.username}")
    except PhoneMigrateError as e:
        logging.warning(f"PhoneMigrate → DC {e.new_dc}")
        await client.disconnect()
        client._dc_id = e.new_dc
        await client.connect()
        await _start_client()
    except FloodWaitError as e:
        logging.warning(f"FloodWait {e.seconds}s on start")
        await asyncio.sleep(e.seconds + random.uniform(120, 300))
        await _start_client()
    except SessionPasswordNeededError:
        logging.info("2FA required, entering…")
        await _start_client()
    except AuthKeyDuplicatedError as e:
        logging.error(
            f"❌ КРИТИЧЕСКАЯ ОШИБКА: AuthKeyDuplicatedError!\n"
            f"Сессия используется одновременно с двух разных IP адресов.\n"
            f"Текущая сессия: {SESSION_PATH}\n"
            f"ENV_MODE: {os.getenv('ENV_MODE', 'production')}\n"
            f"Номер телефона: {phone_number}\n\n"
            f"РЕШЕНИЕ:\n"
            f"1. Если тестируешь локально - убедись, что на сервере бот ОСТАНОВЛЕН\n"
            f"2. Или используй РАЗНЫЕ аккаунты для сервера и локально\n"
            f"3. Для локального теста используй тестовый аккаунт (ENV_MODE=test)\n"
            f"4. Удали старую сессию и создай новую: Remove-Item {SESSION_PATH}.session"
        )
        return
    except Exception as e:
        logging.error(f"Auth error: {e}\n{traceback.format_exc()}")
        return

    logging.info("Бот запущен!")
    intervals = _normalize_intervals(CONFIG['channel_type_intervals'])
    last_check = {t: 0 for t in (0, 1, 2, 3, 4, 5, 6)}
    last_config_check = 0
    last_table_check = 0
    last_connection_check = 0
    base_sleep = min(intervals.values())
    CONNECTION_CHECK_INTERVAL = 300  # Проверка соединения каждые 5 минут

    while True:
        try:
            now = time.time()
            
            # Периодическая проверка соединения
            if now - last_connection_check >= CONNECTION_CHECK_INTERVAL:
                try:
                    await ensure_connected()
                except Exception as e:
                    logging.error(f"Connection check failed: {e}")
                last_connection_check = now
            
            csv_rows = load_csv()
            if now - last_config_check >= CONFIG_CHECK_INTERVAL:
                await update_configs(csv_rows)
                last_config_check = now
                intervals = _normalize_intervals(CONFIG['channel_type_intervals'])
                base_sleep = min(intervals.values())
            if now - last_table_check >= CONFIG['table_scan_interval']:
                await fetch_channels(csv_rows)
                last_table_check = now
            channels = get_tracked_channels()
            for t, interval in intervals.items():
                if now - last_check[t] >= interval:
                    await fetch_unread_messages(channels, t)
                    last_check[t] = now
        except AuthKeyDuplicatedError as e:
            logging.error(
                f"❌ Main loop: AuthKeyDuplicatedError - сессия используется с двух IP!\n"
                f"Останови бота на сервере или используй другой аккаунт.\n"
                f"Сессия: {SESSION_PATH}, ENV_MODE: {os.getenv('ENV_MODE', 'production')}"
            )
            await asyncio.sleep(60)  # Долгая пауза перед следующей попыткой
        except ConnectionError as e:
            logging.error(f"Main loop: Connection lost: {e}, reconnecting...")
            try:
                await ensure_connected()
                await asyncio.sleep(5)  # Небольшая пауза после переподключения
            except Exception as reconnect_error:
                logging.error(f"Main loop: Reconnection failed: {reconnect_error}")
                await asyncio.sleep(30)  # Долгая пауза при неудаче
        except Exception as e:
            logging.error(f"Main loop error: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(10)  # Пауза при любой другой ошибке
        await asyncio.sleep(base_sleep)

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())