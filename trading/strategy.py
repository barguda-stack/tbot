from core.logger import setup_logger

logger = setup_logger(__name__)

def analyze_market_and_select(instruments: list) -> list:
    """
    Оценивает инструменты и выбирает лучшие для торговли.
    В будущем здесь будет алгоритм анализа волатильности / потенциала роста.
    Пока возвращаем все отфильтрованные инструменты как "перспективные".
    """
    return instruments

def get_news_sentiment(ticker: str) -> str:
    """Аналитика новостей по инструментам (заглушка)."""
    # Здесь должен быть парсинг новостей (RSS/API).
    # Ожидаемые значения: 'POSITIVE', 'NEGATIVE', 'NEUTRAL'
    return 'NEUTRAL'

def check_ml_trained(ticker: str) -> bool:
    """Проверяет, обучен ли алгоритм на истории в 1 год для данного тикера."""
    # Заглушка. Пусть только некоторые будут обучены для демонстрации.
    return ticker in ['SBER', 'GAZP', 'LKOH']

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
