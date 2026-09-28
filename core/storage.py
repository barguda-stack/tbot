import os
import json
from core.logger import setup_logger

logger = setup_logger(__name__)

def get_settings() -> dict:
    """Загрузка настроек бота (инструменты, токен) из файла."""
    try:
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding="utf-8") as f:
                settings = json.load(f)
                if "instruments" not in settings:
                    settings["instruments"] = {}
                return settings
    except Exception as e:
        logger.error(f"Ошибка чтения настроек: {e}")
    return {"instruments": {}, "tinkoff_token": "", "api_env": "UNKNOWN"}

def save_settings(settings: dict):
    """Сохранение настроек в файл."""
    try:
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")

def save_bot_state(state: dict):
    """Сохранение состояния бота (баланс, позиции, свечи) в JSON-файл для UI."""
    try:
        with open("bot_state.json", "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния бота: {e}")
