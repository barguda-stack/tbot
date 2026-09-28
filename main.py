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
            try:
                # В новых версиях SDK get_sandbox_accounts deprecate'нута, вызываем через users
                client.users.get_accounts()
            except Exception:
                pass
            logger.info("Токен определен как ПЕСОЧНИЦА (Sandbox).")
            return "sandbox-invest-public-api.tinkoff.ru:443"
    except RequestError as e:
        # Код 16 (UNAUTHENTICATED) значит, что токен не для песочницы
        if "unauthenticated" in str(e).lower():
            logger.info("Ошибка аутентификации в песочнице. Пробуем боевой контур...")
        else:
            logger.warning(f"Неожиданная ошибка при проверке песочницы (возможно сеть): {e}")
            
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

def get_available_instruments(client: Client) -> list:
    """Получает список доступных акций MOEX."""
    logger.info("Получение списка доступных инструментов MOEX...")
    try:
        shares = client.instruments.shares().instruments
        # Фильтруем: только MOEX, доступные для покупки (buy_available_flag)
        # Для начала возьмем топ-10 самых ликвидных (здесь для простоты отбираем несколько известных)
        target_tickers = ['SBER', 'GAZP', 'LKOH', 'YNDX', 'TCSG', 'ROSN', 'MGNT', 'MTSS', 'NVTK', 'SNGSP']
        moex_shares = [
            s for s in shares 
            if s.class_code == 'TQBR' and s.buy_available_flag and s.ticker in target_tickers
        ]
        
        instruments = []
        for s in moex_shares:
            instruments.append({
                "figi": s.figi,
                "ticker": s.ticker,
                "name": s.name,
                "lot": s.lot
            })
        logger.info(f"Найдено подходящих инструментов: {len(instruments)}")
        return instruments
    except RequestError as e:
        logger.error(f"Ошибка получения инструментов: {e}")
        return []

def analyze_market_and_select(client: Client, instruments: list) -> list:
    """Оценивает инструменты и выбирает лучшие для торговли."""
    # В будущем здесь будет алгоритм анализа волатильности / потенциала роста.
    # Пока возвращаем все отфильтрованные инструменты как "перспективные".
    return instruments

def get_news_sentiment(ticker: str) -> str:
    """Аналитика новостей по инструментам (заглушка)."""
    # Здесь должен быть реальный парсинг новостей (например, через RSS или API новостей)
    # Возвращает: 'POSITIVE', 'NEGATIVE' или 'NEUTRAL'
    return 'NEUTRAL'

def run_30_algorithms(ticker: str, candles: list, news_sentiment: str) -> str:
    """
    Выполняет ансамбль из 30 алгоритмов.
    Если 25 алгоритмов говорят 'BUY' -> возвращает 'BUY'
    Если 25 алгоритмов говорят 'SELL' -> возвращает 'SELL'
    Иначе -> 'HOLD'
    """
    # Здесь должна быть реальная интеграция 30 ML / классических алгоритмов.
    # Для целей каркаса возвращаем HOLD.
    buy_votes = 0
    sell_votes = 0
    
    # Псевдо-логика влияния новостей
    if news_sentiment == 'POSITIVE':
        buy_votes += 5
    elif news_sentiment == 'NEGATIVE':
        sell_votes += 5
        
    if buy_votes >= 25:
        return 'BUY'
    elif sell_votes >= 25:
        return 'SELL'
    return 'HOLD'

def get_settings():
    """Загрузка настроек лотов из файла (или значения по умолчанию)."""
    import json
    try:
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения настроек: {e}")
    return {"instruments": {}}

def save_bot_state(state: dict):
    """Сохранение состояния бота в JSON-файл для UI."""
    import json
    try:
        with open("bot_state.json", "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния бота: {e}")

def trading_loop(client: Client, account_id: str):
    """
    Автономный торговый цикл с риск-менеджментом.
    """
    logger.info("Запуск торгового цикла...")
    risk_manager = RiskManager(max_drawdown_percent=2.0)
    
    instruments = get_available_instruments(client)
    selected_instruments = analyze_market_and_select(client, instruments)
    
    error_count = 0
    
    while True:
        try:
            if risk_manager.check_kill_switch():
                time.sleep(30)
                continue
            
            settings = get_settings()
                
            # 1. Проверка баланса и рисков
            balance = get_account_balance(client, account_id)
            if not risk_manager.evaluate_risk(balance):
                continue
            
            # 2. Получение позиций
            try:
                positions = client.operations.get_positions(account_id=account_id)
                open_positions = {p.figi: p.balance for p in positions.securities}
            except Exception as e:
                logger.error(f"Ошибка получения позиций: {e}")
                open_positions = {}
                
            dashboard_data = {
                "timestamp": time.time(),
                "balance": balance,
                "instruments": []
            }
            
            from datetime import datetime, timedelta, timezone
            from tinkoff.invest import CandleInterval
            
            current_time = datetime.now(timezone.utc)
            from_time = current_time - timedelta(days=1)
            
            for inst in selected_instruments:
                figi = inst["figi"]
                ticker = inst["ticker"]
                
                # Читаем настройки для конкретного инструмента
                inst_settings = settings.get("instruments", {}).get(ticker, {})
                is_active = inst_settings.get("active", False)
                max_lots = inst_settings.get("max_lots", 1)
                max_trades = inst_settings.get("max_trades", 5)
                
                # Симуляция проверки обученности ML (заглушка)
                ml_trained = True if ticker in ['SBER', 'GAZP', 'LKOH'] else False
                
                # Получаем цену и свечи
                current_price = get_price(client, figi)
                candles_data = []
                try:
                    candles_response = client.market_data.get_candles(
                        figi=figi,
                        from_=from_time,
                        to=current_time,
                        interval=CandleInterval.CANDLE_INTERVAL_15_MIN
                    )
                    for c in candles_response.candles:
                        candles_data.append({
                            "time": int(c.time.timestamp()),
                            "open": c.open.units + c.open.nano / 1e9,
                            "high": c.high.units + c.high.nano / 1e9,
                            "low": c.low.units + c.low.nano / 1e9,
                            "close": c.close.units + c.close.nano / 1e9
                        })
                except Exception as e:
                    pass
                
                position_balance = open_positions.get(figi, 0)
                invested_amount = position_balance * current_price * inst["lot"]
                
                dashboard_data["instruments"].append({
                    "figi": figi,
                    "ticker": ticker,
                    "name": inst["name"],
                    "lot": inst["lot"],
                    "current_price": current_price,
                    "invested": invested_amount,
                    "position": position_balance,
                    "active": is_active,
                    "max_lots": max_lots,
                    "max_trades": max_trades,
                    "ml_trained": ml_trained,
                    "candles": candles_data
                })
                
                # Торговая логика если инструмент активен и ML обучен
                if is_active and ml_trained:
                    logger.info(f"Анализ {ticker}: Цена = {current_price} руб.")
                    news_sentiment = get_news_sentiment(ticker)
                    signal = run_30_algorithms(ticker, candles_data, news_sentiment)
                    logger.info(f"[{ticker}] Решение алгоритмов: {signal} (Новости: {news_sentiment})")
                    
                    if signal == 'BUY':
                        # Проверка лимита лотов
                        if position_balance < max_lots:
                            logger.info(f"[{ticker}] Сигнал BUY. Отправка ордера на покупку...")
                            # order = client.orders.post_order(...)
                        else:
                            logger.info(f"[{ticker}] Сигнал BUY проигнорирован (достигнут лимит {max_lots} лотов).")
                    elif signal == 'SELL':
                        if position_balance > 0:
                            logger.info(f"[{ticker}] Сигнал SELL. Отправка ордера на продажу...")
                            # order = client.orders.post_order(...)
            
            save_bot_state(dashboard_data)
            
            error_count = 0 # Сброс ошибок при успешном цикле
            time.sleep(15)
            
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
