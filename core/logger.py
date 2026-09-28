import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    """Настройка базового логирования (вывод в файл bot.log и в консоль)"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Чтобы не дублировать логи, если логгер уже настроен
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler("bot.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        
    return logger
