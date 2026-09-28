import os
from dotenv import load_dotenv

from core.logger import setup_logger
from core.client import init_client
from trading.engine import execute_trade_cycle

logger = setup_logger("main")

def main():
    """Точка входа торгового бота."""
    # Загрузка переменных окружения
    load_dotenv()
    TINKOFF_TOKEN = os.getenv("TINKOFF_TOKEN")
    ACCOUNT_ID = os.getenv("ACCOUNT_ID")

    if not TINKOFF_TOKEN:
        logger.error("Токен TINKOFF_TOKEN не задан в переменных окружения (.env).")
        return
        
    logger.info("Инициализация Tinkoff Invest API...")
    
    with init_client(TINKOFF_TOKEN) as client:
        # Если аккаунт не задан жестко в .env, берем первый доступный
        target_account_id = ACCOUNT_ID
        if not target_account_id:
            logger.info("ACCOUNT_ID не предоставлен, получаем список доступных аккаунтов...")
            try:
                accounts = client.users.get_accounts().accounts
                if not accounts:
                    logger.error("Аккаунты для данного токена не найдены.")
                    return
                target_account_id = accounts[0].id
                logger.info(f"Используется аккаунт: {target_account_id}")
            except Exception as e:
                logger.error(f"Ошибка получения аккаунтов: {e}")
                return
            
        # Запуск главного цикла
        execute_trade_cycle(client, target_account_id)

if __name__ == "__main__":
    main()
