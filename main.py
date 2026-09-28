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

KILL_SWITCH_FILE = "kill_switch.flag"

def detect_environment(token: str) -> str:
    """Автоматическое определение типа токена (песочница или боевой)."""
    logger.info("Автоматическое определение среды по токену...")
    
    # Сначала проверяем песочницу
    import tinkoff.invest.constants
    tinkoff.invest.constants.INVEST_GRPC_API = "sandbox-invest-public-api.tinkoff.ru:443"
    
    try:
        with Client(token) as client:
            client.sandbox.get_sandbox_accounts()
            logger.info("Токен определен как ПЕСОЧНИЦА (Sandbox).")
            return "sandbox-invest-public-api.tinkoff.ru:443"
    except RequestError as e:
        # Код 16 (UNAUTHENTICATED) значит, что токен не для песочницы
        if e.code == grpc.StatusCode.UNAUTHENTICATED or "unauthenticated" in str(e).lower():
            logger.info("Ошибка аутентификации в песочнице. Пробуем боевой контур...")
        else:
            logger.warning(f"Неожиданная ошибка при проверке песочницы: {e}")
            
    # Если не песочница, возвращаем боевой адрес
    logger.info("Токен определен как БОЕВОЙ (Production).")
    return "invest-public-api.tinkoff.ru:443"

def init_client(token: str) -> Client:
    """Инициализация и возврат клиента Tinkoff с автоматическим адресом."""
    target = detect_environment(token)
    import tinkoff.invest.constants
    tinkoff.invest.constants.INVEST_GRPC_API = target
    return Client(token)

class RiskManager:
    def __init__(self, max_drawdown_percent: float = 2.0):
        self.max_drawdown_percent = max_drawdown_percent
        self.initial_balance = None
    
    def check_kill_switch(self):
        if os.path.exists(KILL_SWITCH_FILE):
            logger.critical("ВНИМАНИЕ! Активирован Kill Switch (аварийная остановка). Бот приостанавливает торговлю!")
            return True
        return False
        
    def evaluate_risk(self, current_balance: float):
        if self.initial_balance is None:
            self.initial_balance = current_balance
            return True
            
        drawdown = ((self.initial_balance - current_balance) / self.initial_balance) * 100
        if drawdown >= self.max_drawdown_percent:
            logger.critical(f"Превышен лимит просадки: {drawdown:.2f}% (Макс: {self.max_drawdown_percent}%). Активация программного Kill Switch!")
            # Создаем файл для глобальной остановки
            with open(KILL_SWITCH_FILE, 'w') as f:
                f.write("Drawdown limit exceeded")
            return False
        return True

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
    Автономный торговый цикл с риск-менеджментом.
    """
    logger.info("Запуск торгового цикла...")
    risk_manager = RiskManager(max_drawdown_percent=2.0)
    
    # FIGI обыкновенной акции Сбербанка (SBER) как пример инструмента
    SBER_FIGI = "BBG004730N88"
    
    error_count = 0
    
    while True:
        try:
            if risk_manager.check_kill_switch():
                time.sleep(30)
                continue
                
            # 1. Проверка баланса и рисков
            balance = get_account_balance(client, account_id)
            if not risk_manager.evaluate_risk(balance):
                continue
            
            # 2. Получение текущей цены актива
            sber_price = get_price(client, SBER_FIGI)
            logger.info(f"Анализ актива (SBER): Цена = {sber_price} руб. Текущий баланс = {balance:.2f} руб.")
            
            # 3. Логика стратегии (каркас)
            # Здесь бот будет вызывать ML-модели или индикаторы (SMA, RSI)
            if sber_price > 0:
                # Временно выводим инфо вместо реальной покупки
                logger.info(f"Сигналов на вход нет. Лимит риска соблюден.")
            
            error_count = 0 # Сброс ошибок при успешном цикле
            time.sleep(60)
            
        except RequestError as e:
            error_count += 1
            wait_time = min(10 * (2 ** error_count), 300) # Exponential backoff до 5 минут
            logger.error(f"Ошибка API Тинькофф: {e}. Повтор через {wait_time} сек...")
            time.sleep(wait_time)
        except Exception as e:
            logger.critical(f"Критическая ошибка в торговом цикле: {e}")
            time.sleep(30)

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
