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
        # Если аккаунт не задан жестко в .env, берем первый доступный непустой
        target_account_id = ACCOUNT_ID
        if not target_account_id:
            logger.info("ACCOUNT_ID не предоставлен, получаем список доступных аккаунтов...")
            try:
                accounts = client.users.get_accounts().accounts
                if not accounts:
                    logger.error("Аккаунты для данного токена не найдены.")
                    return
                
                logger.info(f"Найдено {len(accounts)} аккаунтов. Ищем непустой...")
                target_account_id = accounts[0].id # Фолбэк на первый
                
                # Ищем аккаунт с положительным балансом или позициями
                for acc in accounts:
                    try:
                        portfolio = client.operations.get_portfolio(account_id=acc.id)
                        total_amt = portfolio.total_amount_portfolio.units + (portfolio.total_amount_portfolio.nano / 1e9)
                        if total_amt > 0:
                            target_account_id = acc.id
                            logger.info(f"Выбран аккаунт {target_account_id} с балансом: {total_amt}")
                            break
                    except Exception as e:
                        logger.debug(f"Пропуск аккаунта {acc.id}: {e}")
                        
                logger.info(f"Итоговый рабочий аккаунт: {target_account_id}")
            except Exception as e:
                logger.error(f"Ошибка получения аккаунтов: {e}")
                return
            
        # Запуск главного цикла
        execute_trade_cycle(client, target_account_id)

if __name__ == "__main__":
    main()
