"""Упрощенные процессоры для обработки сообщений разных типов каналов"""
import logging
import re
from typing import Dict, Any, Optional, List

# === КОНСТАНТЫ ТИПОВ КАНАЛОВ ===
CHANNEL_TYPE_FILTERED = 0
CHANNEL_TYPE_WHITELIST = 1
CHANNEL_TYPE_STATS = 2
CHANNEL_TYPE_LONGCHECK = 3
CHANNEL_TYPE_RANKS = 4
CHANNEL_TYPE_WHITELIST2 = 5
CHANNEL_TYPE_TYPE2 = 6

# Регулярное выражение для парсинга сумм
_AMOUNT_RE = re.compile(r'\$(\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)([KkMmBb]?)')

def _prepare_post_data(message, ch_link: str, channel: str, channel_type: int, 
                      msg_text: Optional[str] = None, is_advertisement: bool = False,
                      blacklisted: bool = False) -> Dict[str, Any]:
    """
    Подготавливает данные поста для сохранения в БД.
    
    Args:
        message: Объект сообщения Telethon
        ch_link: Ссылка на канал (без @)
        channel: Название канала (с @)
        channel_type: Тип канала
        msg_text: Текст сообщения (если None, будет извлечен из message)
        is_advertisement: Является ли пост рекламой
        blacklisted: Попал ли пост в blacklist
    
    Returns:
        Словарь с данными поста
    """
    if msg_text is None:
        if message.text:
            msg_text = message.text.decode('utf-8') if isinstance(message.text, bytes) else message.text
        else:
            msg_text = None
    
    has_media = bool(message.video or message.voice or message.photo or 
                    message.document or message.poll)
    
    return {
        'channel': channel,
        'channel_type': channel_type,
        'message_id': message.id,
        'post_url': f"https://t.me/{ch_link}/{message.id}",
        'text': msg_text,
        'text_length': len(msg_text) if msg_text else 0,
        'published_at': message.date,
        'is_advertisement': is_advertisement,
        'is_forwarded': False,  # Будет обновлено после пересылки
        'has_media': has_media,
        'blacklisted': blacklisted
    }

def parse_amount(text: str) -> Optional[float]:
    """Парсит сумму из текста сообщения"""
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    num = float(m.group(1).replace(',', '').replace(' ', ''))
    multipliers = {'B': 1_000_000_000, 'M': 1_000_000, 'K': 1_000}
    return num * multipliers.get(m.group(2).upper(), 1)

# === ПРОСТЫЕ ФУНКЦИИ ОБРАБОТКИ ===

async def process_whitelist_message(message, peer, ch_link: str, channel_type: int, counters: dict, 
                                     safe_forward_func, is_blacklisted_func=None, is_advertisement_func=None,
                                     is_advertisement_post_func=None, add_advertisement_post_func=None,
                                     config: dict = None, channel: str = None, posts_batch: Optional[List[Dict]] = None, **kwargs):
    """Whitelist каналы - пересылает все сообщения"""
    forwarded = await safe_forward_func(message.id, peer, ch_link, channel_type, counters)
    # Сохраняем все посты из whitelist
    if posts_batch is not None:
        msg_text = None
        if message.text:
            msg_text = message.text.decode('utf-8') if isinstance(message.text, bytes) else message.text
        post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                      msg_text=msg_text, is_advertisement=False, blacklisted=False)
        post_data['is_forwarded'] = forwarded
        posts_batch.append(post_data)
    return forwarded

async def process_filtered_message(message, peer, ch_link: str, channel_type: int, counters: dict,
                                   safe_forward_func, is_blacklisted_func, is_advertisement_func,
                                   is_advertisement_post_func, add_advertisement_post_func,
                                   config: dict, channel: str, posts_batch: Optional[List[Dict]] = None, **kwargs):
    """Filtered и Longcheck каналы - фильтрует через AI"""
    # Проверка на уже помеченную рекламу
    if is_advertisement_post_func(message.id):
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): AD tagged, skip")
        counters['ads'] += 1
        counters['skipped'] += 1
        # Сохраняем пост, помеченный как реклама ранее
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          is_advertisement=True, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    # Медиа без текста - пропускаем
    has_media = (message.video or message.voice or message.photo or 
                 message.document or message.poll)
    if has_media and not message.text:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): Media-only or poll, skip")
        counters['skipped'] += 1
        # Сохраняем медиа-посты без текста
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=None, is_advertisement=False, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    # Сообщения без текста - пересылаем
    if not message.text:
        forwarded = await safe_forward_func(
            message.id, peer, ch_link, channel_type, counters,
            log_prefix=f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): FW no-text → {config['target_channel']}: {message.id}"
        )
        # Сохраняем пост без текста
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=None, is_advertisement=False, blacklisted=False)
            post_data['is_forwarded'] = forwarded
            posts_batch.append(post_data)
        return forwarded
    
    # Получаем текст
    msg_text = message.text.decode('utf-8') if isinstance(message.text, bytes) else message.text
    if not msg_text:
        counters['skipped'] += 1
        return False
    
    # Проверка blacklist
    is_blacklisted_result = await is_blacklisted_func(msg_text)
    if is_blacklisted_result:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): Blacklist skip")
        counters['skipped'] += 1
        # Сохраняем заблокированные посты
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=True)
            posts_batch.append(post_data)
        return False
    
    # Проверка на рекламу через AI
    is_ad_result = await is_advertisement_func(msg_text)
    if is_ad_result:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): AD detected, skip")
        add_advertisement_post_func(message.id, channel)
        counters['ads'] += 1
        counters['skipped'] += 1
        # Сохраняем рекламные посты
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=True, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    # Проверка минимальной длины
    if len(msg_text.strip()) < config['min_length']:
        counters['skipped'] += 1
        # Сохраняем короткие посты
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    # Все проверки пройдены - пересылаем
    forwarded = await safe_forward_func(message.id, peer, ch_link, channel_type, counters)
    # Сохраняем успешно обработанные посты
    if posts_batch is not None:
        post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                      msg_text=msg_text, is_advertisement=False, blacklisted=False)
        post_data['is_forwarded'] = forwarded
        posts_batch.append(post_data)
    return forwarded

async def process_stats_message(message, peer, ch_link: str, channel_type: int, counters: dict,
                                safe_forward_func, is_blacklisted_func=None, is_advertisement_func=None,
                                is_advertisement_post_func=None, add_advertisement_post_func=None,
                                config: dict = None, channel: str = None, posts_batch: Optional[List[Dict]] = None, **kwargs):
    """Stats каналы - фильтрация по суммам"""
    if config is None:
        raise ValueError("config parameter is required for process_stats_message")
    # Сообщения без текста - пересылаем
    if not message.text:
        forwarded = await safe_forward_func(
            message.id, peer, ch_link, channel_type, counters, 
            use_short_delay=False
        )
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=None, is_advertisement=False, blacklisted=False)
            post_data['is_forwarded'] = forwarded
            posts_batch.append(post_data)
        return forwarded
    
    msg_text = message.text.decode('utf-8') if isinstance(message.text, bytes) else message.text
    if not msg_text:
        counters['skipped'] += 1
        return False
    
    # Парсим сумму
    amount = parse_amount(msg_text)
    if amount is None:
        counters['skipped'] += 1
        # Сохраняем посты без суммы
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    upper = msg_text.upper()
    
    # Проверка для BTC/ETH
    if 'BTC' in upper or 'ETH' in upper:
        if amount > config['btc_eth_threshold']:
            forwarded = await safe_forward_func(
                message.id, peer, ch_link, channel_type, counters,
                log_prefix=f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): FW stats BTC/ETH {amount} → {config['target_channel']}",
                use_short_delay=False
            )
            if posts_batch is not None:
                post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                              msg_text=msg_text, is_advertisement=False, blacklisted=False)
                post_data['is_forwarded'] = forwarded
                posts_batch.append(post_data)
            return forwarded
        else:
            counters['skipped'] += 1
            # Сохраняем посты с малой суммой BTC/ETH
            if posts_batch is not None:
                post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                              msg_text=msg_text, is_advertisement=False, blacklisted=False)
                posts_batch.append(post_data)
            return False
    
    # Проверка для других монет
    if amount > config['other_coin_threshold']:
        forwarded = await safe_forward_func(
            message.id, peer, ch_link, channel_type, counters,
            log_prefix=f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): FW stats {amount} → {config['target_channel']}",
            use_short_delay=False
        )
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=False)
            post_data['is_forwarded'] = forwarded
            posts_batch.append(post_data)
        return forwarded
    else:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): Skip stats other {amount} < {config['other_coin_threshold']}")
        counters['skipped'] += 1
        # Сохраняем посты с малой суммой других монет
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=False)
            posts_batch.append(post_data)
        return False

async def process_ranks_message(message, peer, ch_link: str, channel_type: int, counters: dict,
                                 safe_forward_func, is_blacklisted_func=None, is_advertisement_func=None,
                                 is_advertisement_post_func=None, add_advertisement_post_func=None,
                                 config: dict = None, channel: str = None, posts_batch: Optional[List[Dict]] = None, **kwargs):
    """Ranks каналы - фильтрует медиа без текста и blacklist"""
    if config is None:
        raise ValueError("config parameter is required for process_ranks_message")
    if is_blacklisted_func is None:
        raise ValueError("is_blacklisted_func parameter is required for process_ranks_message")
    # Медиа без текста - пропускаем
    has_media = (message.video or message.voice or message.photo or 
                 message.document or message.poll)
    if has_media and not message.text:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): Media-only or poll, skip")
        counters['skipped'] += 1
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=None, is_advertisement=False, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    # Сообщения без текста - пересылаем
    if not message.text:
        forwarded = await safe_forward_func(
            message.id, peer, ch_link, channel_type, counters,
            log_prefix=f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): FW no-text → {config['target_channel']}: {message.id}"
        )
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=None, is_advertisement=False, blacklisted=False)
            post_data['is_forwarded'] = forwarded
            posts_batch.append(post_data)
        return forwarded
    
    # Извлечение текста
    msg_text = message.text.decode('utf-8') if isinstance(message.text, bytes) else message.text
    if not msg_text:
        counters['skipped'] += 1
        return False
    
    # Проверка blacklist
    is_blacklisted_result = await is_blacklisted_func(msg_text)
    if is_blacklisted_result:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): Blacklist skip")
        counters['skipped'] += 1
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=True)
            posts_batch.append(post_data)
        return False
    
    # Все проверки пройдены - пересылаем
    forwarded = await safe_forward_func(message.id, peer, ch_link, channel_type, counters)
    if posts_batch is not None:
        post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                      msg_text=msg_text, is_advertisement=False, blacklisted=False)
        post_data['is_forwarded'] = forwarded
        posts_batch.append(post_data)
    return forwarded

async def process_whitelist2_message(message, peer, ch_link: str, channel_type: int, counters: dict,
                                      safe_forward_func, is_blacklisted_func=None, is_advertisement_func=None,
                                      is_advertisement_post_func=None, add_advertisement_post_func=None,
                                      config: dict = None, channel: str = None, posts_batch: Optional[List[Dict]] = None, **kwargs):
    """Whitelist2 каналы - как whitelist, но с дополнительными фильтрами"""
    if config is None:
        raise ValueError("config parameter is required for process_whitelist2_message")
    if is_blacklisted_func is None:
        raise ValueError("is_blacklisted_func parameter is required for process_whitelist2_message")
    # Медиа без текста - пропускаем
    has_media = (message.video or message.voice or message.photo or 
                 message.document or message.poll)
    if has_media and not message.text:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): Media-only or poll, skip")
        counters['skipped'] += 1
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=None, is_advertisement=False, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    # Сообщения без текста - пересылаем
    if not message.text:
        forwarded = await safe_forward_func(
            message.id, peer, ch_link, channel_type, counters,
            log_prefix=f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): FW no-text → {config['target_channel']}: {message.id}"
        )
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=None, is_advertisement=False, blacklisted=False)
            post_data['is_forwarded'] = forwarded
            posts_batch.append(post_data)
        return forwarded
    
    # Извлечение текста
    msg_text = message.text.decode('utf-8') if isinstance(message.text, bytes) else message.text
    if not msg_text:
        counters['skipped'] += 1
        return False
    
    # Проверка blacklist
    is_blacklisted_result = await is_blacklisted_func(msg_text)
    if is_blacklisted_result:
        logging.info(f"https://t.me/{ch_link}/{message.id} (Type {channel_type}): Blacklist skip")
        counters['skipped'] += 1
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=True)
            posts_batch.append(post_data)
        return False
    
    # Проверка минимальной длины (используем min_length_wl)
    min_length_wl = config.get('min_length_wl', config.get('min_length', 95))
    if len(msg_text.strip()) < min_length_wl:
        counters['skipped'] += 1
        if posts_batch is not None:
            post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                          msg_text=msg_text, is_advertisement=False, blacklisted=False)
            posts_batch.append(post_data)
        return False
    
    # Все проверки пройдены - пересылаем
    forwarded = await safe_forward_func(message.id, peer, ch_link, channel_type, counters)
    if posts_batch is not None:
        post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                      msg_text=msg_text, is_advertisement=False, blacklisted=False)
        post_data['is_forwarded'] = forwarded
        posts_batch.append(post_data)
    return forwarded

async def process_type2_message(message, peer, ch_link: str, channel_type: int, counters: dict,
                                 safe_forward_func, is_blacklisted_func=None, is_advertisement_func=None,
                                 is_advertisement_post_func=None, add_advertisement_post_func=None,
                                 config: dict = None, channel: str = None, posts_batch: Optional[List[Dict]] = None, **kwargs):
    """Type2 каналы - задел на будущее, пока без фильтров (пересылает все)"""
    # Пока просто пересылаем все, как whitelist
    forwarded = await safe_forward_func(message.id, peer, ch_link, channel_type, counters)
    if posts_batch is not None:
        msg_text = None
        if message.text:
            msg_text = message.text.decode('utf-8') if isinstance(message.text, bytes) else message.text
        post_data = _prepare_post_data(message, ch_link, channel, channel_type, 
                                      msg_text=msg_text, is_advertisement=False, blacklisted=False)
        post_data['is_forwarded'] = forwarded
        posts_batch.append(post_data)
    return forwarded

# Словарь процессоров вместо фабрики
MESSAGE_PROCESSORS = {
    CHANNEL_TYPE_WHITELIST: process_whitelist_message,
    CHANNEL_TYPE_FILTERED: process_filtered_message,
    CHANNEL_TYPE_LONGCHECK: process_filtered_message,  # Использует ту же логику
    CHANNEL_TYPE_STATS: process_stats_message,
    CHANNEL_TYPE_RANKS: process_ranks_message,
    CHANNEL_TYPE_WHITELIST2: process_whitelist2_message,
    CHANNEL_TYPE_TYPE2: process_type2_message,
}
