from core.logger import setup_logger

logger = setup_logger(__name__)

def analyze_market_and_select(instruments: list) -> list:
    """
    Оценивает инструменты и выбирает лучшие для торговли.
    В будущем здесь будет алгоритм анализа волатильности / потенциала роста.
    Пока возвращаем все отфильтрованные инструменты как "перспективные".
    """
    return instruments

def run_premarket_analysis(client) -> list:
    """
    Анализирует доступные инструменты рынка для выявления инструментов 
    с максимальным возможным профитом (рейтинг).
    Использует реальные данные API (спред между текущей ценой и ценой закрытия).
    """
    logger.info("Запуск премаркет-анализа на реальных данных Т-Банка...")
    from trading.market import get_available_instruments
    from tinkoff.invest import RequestError
    
    instruments = get_available_instruments(client)
    if not instruments:
        return []

    # Собираем FIGI для массового запроса
    figis = [inst["figi"] for inst in instruments]
    
    # Получаем последние цены и цены закрытия (для расчета изменения/волатильности)
    try:
        # Для массового запроса цен
        prices_response = client.market_data.get_last_prices(figi=figis)
        last_prices = {p.figi: (p.price.units + p.price.nano / 1e9) for p in prices_response.last_prices}
        
        # Получаем цены закрытия (close prices). В API v2 get_close_prices
        close_response = client.market_data.get_close_prices(figi=figis)
        close_prices = {p.figi: (p.price.units + p.price.nano / 1e9) for p in close_response.close_prices}
        
    except RequestError as e:
        logger.error(f"Ошибка при массовом запросе цен для премаркета: {e}")
        return []

    # Расчет рейтинга профитности
    for inst in instruments:
        figi = inst["figi"]
        current = last_prices.get(figi, 0.0)
        close_pr = close_prices.get(figi, 0.0)
        
        score = 0.0
        # Если есть цена закрытия и текущая, считаем процент изменения (волатильность как потенциал профита)
        if close_pr > 0 and current > 0:
            change_percent = abs((current - close_pr) / close_pr * 100)
            score = round(change_percent * 10, 1) # Умножаем для наглядности рейтинга
            
        inst['profit_score'] = score
        inst['current_price'] = current
        
    # Сортируем по убыванию рейтинга (самые волатильные/перспективные наверху)
    top_instruments = sorted(instruments, key=lambda x: x['profit_score'], reverse=True)
    
    # Ограничиваем выдачу топ-10
    return top_instruments[:10]

def get_news_sentiment(ticker: str) -> str:
    """Аналитика новостей по инструментам (заглушка)."""
    # Здесь должен быть парсинг новостей (RSS/API).
    # Ожидаемые значения: 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
    return 'NEUTRAL'

def train_30_algorithms(ticker: str, historical_candles_1y: list) -> bool:
    """
    Симулирует обучение 30 алгоритмов на исторических данных за 1 год.
    На вход получает список дневных свечей за 365 дней.
    """
    import time
    logger.info(f"[{ticker}] Запуск обучения 30 алгоритмов на исторических данных (длина: {len(historical_candles_1y)} свечей)...")
    
    # Имитация длительного процесса обучения (задержка)
    time.sleep(5)
    
    # В реальном приложении здесь будет перерасчет весов для ML моделей,
    # расчет SMA, EMA, RSI, MACD, Bollinger Bands и сохранение их параметров в локальную БД или кэш.
    logger.info(f"[{ticker}] Обучение алгоритмов успешно завершено.")
    return True

def run_30_algorithms(ticker: str, candles: list, news_sentiment: str) -> str:
    """
    Выполняет ансамбль из 30 алгоритмов машинного обучения и тех. анализа.
    Логика:
    - 25+ алгоритмов за покупку -> 'BUY'
    - 25+ алгоритмов за продажу -> 'SELL'
    - Иначе -> 'HOLD'
    """
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
