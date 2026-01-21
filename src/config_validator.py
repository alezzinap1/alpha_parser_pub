"""Простая валидация конфигурации без Pydantic"""
import logging
import ast
from typing import Dict, Any

def validate_config_value(key: str, value: Any, config: Dict[str, Any]) -> Any:
    """Простая валидация одного значения конфига"""
    try:
        # Целочисленные поля
        if key in ['table_scan_interval', 'message_scan_interval', 'min_length', 'min_length_wl',
                   'max_messages_per_channel', 'csv_timeout', 'max_null_hash_fixes']:
            if isinstance(value, str):
                val = int(value.replace('_', '').replace(' ', ''))
            else:
                val = int(value)
            
            # Дополнительные проверки
            if key == 'message_scan_interval' and val < 30:
                val = 30
            elif key in ['table_scan_interval', 'min_length', 'min_length_wl'] and val < 1:
                val = 1
            elif key in ['csv_timeout', 'max_null_hash_fixes'] and val < 1:
                val = 1
            
            return val
        
        # Пороговые значения
        elif key in ['btc_eth_threshold', 'other_coin_threshold']:
            if isinstance(value, str):
                val = int(value.replace('_', '').replace(' ', ''))
            else:
                val = int(value)
            if val < 0:
                raise ValueError(f"{key} must be >= 0")
            return val
        
        # Float поля
        elif key in ['sleep_between_channels_min', 'sleep_between_channels_max']:
            if isinstance(value, str):
                val = float(value.replace(',', '.'))
            else:
                val = float(value)
            if val < 0:
                raise ValueError(f"{key} must be >= 0")
            return val
        
        # Boolean поле
        elif key == 'log_channel_count_changes_only':
            if isinstance(value, str):
                lowered = value.strip().lower()
                return lowered in ('true', '1', 'yes', 'on')
            return bool(value)
        
        # Строковые поля с проверками
        elif key == 'target_channel':
            val = str(value).strip()
            if not val.startswith('@'):
                raise ValueError("target_channel must start with '@'")
            return val
        
        elif key == 'user_prompt':
            val = str(value)
            if '{text}' not in val:
                raise ValueError("user_prompt must contain '{text}' placeholder")
            return val
        
        elif key in ['system_prompt', 'user_prompt']:
            # Декодирование для CSV (если нужно)
            if isinstance(value, bytes):
                try:
                    return value.encode('latin1').decode('utf-8')
                except:
                    return value.decode('utf-8', errors='ignore')
            return str(value)
        
        # Список blacklist_words
        elif key == 'blacklist_words':
            if isinstance(value, str):
                if value.strip().startswith('['):
                    try:
                        parsed = ast.literal_eval(value.strip())
                        if isinstance(parsed, list):
                            return [str(w) for w in parsed if w]
                    except (ValueError, SyntaxError):
                        pass
                # Разделяем по запятым
                return [w.strip() for w in value.split(',') if w.strip()]
            elif isinstance(value, list):
                return [str(w) for w in value if w]
            return []
        
        # Словарь channel_type_intervals
        elif key == 'channel_type_intervals':
            if isinstance(value, str):
                try:
                    parsed = ast.literal_eval(value.strip())
                    if isinstance(parsed, dict):
                        # Валидация значений
                        result = {}
                        for k, v in parsed.items():
                            try:
                                iv = int(v)
                                result[k] = max(60, iv) if k != 'stats' else max(30, iv)
                            except (ValueError, TypeError):
                                continue
                        return result
                except (ValueError, SyntaxError):
                    pass
            elif isinstance(value, dict):
                # Валидация существующего словаря
                result = {}
                for k, v in value.items():
                    try:
                        iv = int(v)
                        result[k] = max(60, iv) if k != 'stats' else max(30, iv)
                    except (ValueError, TypeError):
                        continue
                return result
            return config.get(key, {})
        
        # Остальные строки
        else:
            return str(value) if value else ''
            
    except (ValueError, TypeError) as e:
        logging.warning(f"Некорректное значение для {key}: {value}, ошибка: {e}")
        raise

def validate_and_update_config(config_dict: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Простая валидация и обновление конфигурации.
    
    Args:
        config_dict: Текущая конфигурация
        updates: Обновления из CSV
    
    Returns:
        Обновленный словарь конфигурации
    """
    result = config_dict.copy()
    updated = False
    
    for key, value in updates.items():
        if key not in config_dict:
            logging.warning(f"Неизвестный ключ конфигурации: {key}")
            continue
        
        try:
            new_value = validate_config_value(key, value, result)
            if result.get(key) != new_value:
                result[key] = new_value
                updated = True
        except (ValueError, TypeError) as e:
            logging.warning(f"Ошибка валидации {key}: {e}, используется текущее значение")
            continue
    
    if updated:
        logging.info(f"Конфигурация обновлена: {list(updates.keys())}")
    
    return result
