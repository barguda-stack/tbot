import os
import time
import logging
from dotenv import load_dotenv

from tinkoff.invest import Client, RequestError, PortfolioResponse, PositionsResponse
from tinkoff.invest.constants import INVEST_GRPC_API

# Настройка базового логирования (вывод в файл bot.log и в консоль)
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env
load_dotenv()
TINKOFF_TOKEN = os.getenv("TINKOFF_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
# INVEST_GRPC_API - это контур для реальной торговли. При необходимости можно изменить на INVEST_GRPC_API_SANDBOX
TARGET = os.getenv("TINKOFF_TARGET", INVEST_GRPC_API) 


def init_client(token: str) -> Client:
    """Инициализация и возврат клиента Tinkoff."""
    logger.info("Инициализация клиента Tinkoff...")
    # Присваиваем константе адрес песочницы, так как в старой версии API 
    # аргумент target в Client не поддерживается
    import tinkoff.invest.constants
    tinkoff.invest.constants.INVEST_GRPC_API = TARGET
    return Client(token)

def get_account_balance(client: Client, account_id: str) -> float:
    """
    Получение баланса портфеля для указанного account_id.
    Это помогает убедиться, что мы торгуем без плеча, используя только доступные средства.
    """
    logger.info(f"Запрос баланса для аккаунта {account_id}...")
    try:
        portfolio: PortfolioResponse = client.operations.get_portfolio(account_id=account_id)
        
        # Пример получения общей суммы в портфеле (при необходимости можно отфильтровать по валюте)
        total_amount = portfolio.total_amount_portfolio.units + (portfolio.total_amount_portfolio.nano / 1e9)
        logger.info(f"Общая стоимость портфеля: {total_amount}")
        
        return total_amount
    
    except RequestError as e:
        logger.error(f"Ошибка при получении портфеля: {e}")
        return 0.0

def get_price(client: Client, figi: str) -> float:
    """Получает последнюю цену по заданному FIGI."""
    try:
        prices = client.market_data.get_last_prices(figi=[figi])
        if prices.last_prices:
            # Конвертируем Quotation (units и nano) в float
            price_obj = prices.last_prices[0].price
            return price_obj.units + price_obj.nano / 1e9
    except RequestError as e:
        logger.error(f"Ошибка при получении цены: {e}")
    return 0.0

def trading_loop(client: Client, account_id: str):
    """
    Рабочий торговый цикл. Для начала мы просто получаем баланс и цену акции.
    """
    logger.info("Запуск торгового цикла...")
    
    # FIGI обыкновенной акции Сбербанка (SBER)
    SBER_FIGI = "BBG004730N88"
    
    while True:
        try:
            # 1. Проверка баланса
            balance = get_account_balance(client, account_id)
            
            # 2. Получение текущей цены Сбербанка
            sber_price = get_price(client, SBER_FIGI)
            logger.info(f"Текущая цена Сбербанка (FIGI: {SBER_FIGI}): {sber_price} руб.")
            
            # 3. Логика стратегии
            # Здесь будет ваша торговая логика (покупка/продажа)
            if sber_price > 0:
                logger.info(f"Следим за ценой. Баланс позволяет купить {int(balance // sber_price)} акций.")
            
            logger.info("Ожидание перед следующим циклом проверки...")
            time.sleep(60) # Ждем 60 секунд перед следующей проверкой
            
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в торговом цикле: {e}")
            time.sleep(10) # Короткая пауза при ошибке перед повторной попыткой

def main():
    if not TINKOFF_TOKEN:
        logger.error("Токен TINKOFF_TOKEN не задан в переменных окружения.")
        return
        
    logger.info("Запуск бота...")
    
    with init_client(TINKOFF_TOKEN) as client:
        # Если ACCOUNT_ID не задан, пытаемся получить первый доступный аккаунт
        target_account_id = ACCOUNT_ID
        if not target_account_id:
            logger.info("ACCOUNT_ID не предоставлен, получаем список доступных аккаунтов...")
            accounts = client.users.get_accounts().accounts
            if not accounts:
                logger.error("Аккаунты для данного токена не найдены.")
                return
            target_account_id = accounts[0].id
            logger.info(f"Используется первый доступный аккаунт: {target_account_id}")
            
        trading_loop(client, target_account_id)

if __name__ == "__main__":
    main()
