import os
import json
from core.logger import setup_logger

logger = setup_logger(__name__)

def get_settings() -> dict:
    """Загрузка настроек лотов и активности инструментов из файла."""
    try:
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения настроек: {e}")
    return {"instruments": {}}

def save_bot_state(state: dict):
    """Сохранение состояния бота (баланс, позиции, свечи) в JSON-файл для UI."""
    try:
        with open("bot_state.json", "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния бота: {e}")
