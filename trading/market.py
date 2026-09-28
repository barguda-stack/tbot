from tinkoff.invest import Client, RequestError, PortfolioResponse, CandleInterval
from core.logger import setup_logger

logger = setup_logger(__name__)

def get_account_balance(client: Client, account_id: str) -> float:
    """Получение общего баланса портфеля для контроля рисков."""
    logger.info(f"Запрос баланса для аккаунта {account_id}...")
    try:
        portfolio: PortfolioResponse = client.operations.get_portfolio(account_id=account_id)
        total_amount = portfolio.total_amount_portfolio.units + (portfolio.total_amount_portfolio.nano / 1e9)
        logger.info(f"Общая стоимость портфеля: {total_amount:.2f} ₽")
        return total_amount
    except RequestError as e:
        logger.error(f"Ошибка при получении портфеля: {e}")
        return 0.0

def get_price(client: Client, figi: str) -> float:
    """Получает последнюю цену по заданному FIGI."""
    try:
        prices = client.market_data.get_last_prices(figi=[figi])
        if prices.last_prices:
            price_obj = prices.last_prices[0].price
            return price_obj.units + price_obj.nano / 1e9
    except RequestError as e:
        logger.error(f"Ошибка при получении цены: {e}")
    return 0.0

def get_available_instruments(client: Client) -> list:
    """Получает список доступных ликвидных акций MOEX."""
    logger.info("Получение списка доступных инструментов MOEX...")
    try:
        shares = client.instruments.shares().instruments
        # Базовый топ-10 ликвидных бумаг РФ
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

def get_historical_data_1y(client: Client, figi: str) -> list:
    """Получает дневные свечи за последний год для обучения алгоритмов."""
    logger.info(f"Запрос исторической даты за 1 год для {figi}...")
    from datetime import datetime, timedelta, timezone
    
    current_time = datetime.now(timezone.utc)
    from_time = current_time - timedelta(days=365)
    
    candles_data = []
    try:
        candles_response = client.market_data.get_candles(
            figi=figi,
            from_=from_time,
            to=current_time,
            interval=CandleInterval.CANDLE_INTERVAL_DAY
        )
        for c in candles_response.candles:
            candles_data.append({
                "time": int(c.time.timestamp()),
                "open": c.open.units + c.open.nano / 1e9,
                "high": c.high.units + c.high.nano / 1e9,
                "low": c.low.units + c.low.nano / 1e9,
                "close": c.close.units + c.close.nano / 1e9,
                "volume": c.volume
            })
        logger.info(f"Собрано {len(candles_data)} дневных свечей для {figi}")
    except Exception as e:
        logger.error(f"Ошибка получения истории за 1 год для {figi}: {e}")
        
    return candles_data

def get_candles_15m_1d(client: Client, figi: str) -> list:
    """Получает 15-минутные свечи за последние сутки."""
    from datetime import datetime, timedelta, timezone
    
    current_time = datetime.now(timezone.utc)
    from_time = current_time - timedelta(days=1)
    
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
        logger.error(f"Ошибка получения свечей для {figi}: {e}")
        
    return candles_data

def get_open_positions(client: Client, account_id: str) -> dict:
    """Возвращает словарь {figi: balance} с открытыми позициями."""
    try:
        positions = client.operations.get_positions(account_id=account_id)
        return {p.figi: p.balance for p in positions.securities}
    except Exception as e:
        logger.error(f"Ошибка получения позиций: {e}")
        return {}
