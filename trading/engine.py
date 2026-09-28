import time
from tinkoff.invest import Client, RequestError
from core.logger import setup_logger
from core.risk import RiskManager
from core.storage import get_settings, save_bot_state
from trading import market, strategy

logger = setup_logger(__name__)

def execute_trade_cycle(client: Client, account_id: str):
    """Основной автономный торговый цикл."""
    logger.info("Запуск торгового цикла...")
    risk_manager = RiskManager(max_drawdown_percent=2.0)
    
    # 1. Анализ рынка
    all_instruments = market.get_available_instruments(client)
    selected_instruments = strategy.analyze_market_and_select(all_instruments)
    
    error_count = 0
    
    while True:
        try:
            # 2. Проверка аварийной остановки (Kill Switch)
            if risk_manager.check_kill_switch():
                time.sleep(30)
                continue
            
            # Читаем пользовательские настройки из UI
            settings = get_settings()
            
            # 3. Общий риск-менеджмент
            balance = market.get_account_balance(client, account_id)
            if not risk_manager.evaluate_risk(balance):
                time.sleep(30)
                continue
            
            # 4. Получение открытых позиций
            open_positions = market.get_open_positions(client, account_id)
            
            dashboard_data = {
                "timestamp": time.time(),
                "balance": balance,
                "instruments": []
            }
            
            # 5. Анализ каждого инструмента
            for inst in selected_instruments:
                figi = inst["figi"]
                ticker = inst["ticker"]
                
                # Загрузка локальных настроек инструмента
                inst_settings = settings.get("instruments", {}).get(ticker, {})
                is_active = inst_settings.get("active", False)
                max_lots = inst_settings.get("max_lots", 1)
                max_trades = inst_settings.get("max_trades", 5)
                
                # Статус обучения
                ml_trained = strategy.check_ml_trained(ticker)
                
                # Рыночные данные
                current_price = market.get_price(client, figi)
                candles_data = market.get_candles_15m_1d(client, figi)
                position_balance = open_positions.get(figi, 0)
                invested_amount = position_balance * current_price * inst["lot"]
                
                # Подготовка данных для UI
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
                
                # 6. Принятие решений (если инструмент разрешен к торгам)
                if is_active and ml_trained:
                    logger.info(f"Анализ {ticker}: Цена = {current_price:.2f} ₽")
                    news_sentiment = strategy.get_news_sentiment(ticker)
                    signal = strategy.run_30_algorithms(ticker, candles_data, news_sentiment)
                    logger.info(f"[{ticker}] Сигнал: {signal} (Новости: {news_sentiment})")
                    
                    if signal == 'BUY':
                        if position_balance < max_lots:
                            logger.info(f"[{ticker}] Отправка ордера на ПОКУПКУ...")
                            # order = client.orders.post_order(...)
                        else:
                            logger.warning(f"[{ticker}] Покупка отменена: достигнут лимит лотов ({max_lots}).")
                    elif signal == 'SELL':
                        if position_balance > 0:
                            logger.info(f"[{ticker}] Отправка ордера на ПРОДАЖУ...")
                            # order = client.orders.post_order(...)
            
            # Сохранение состояния для фронтенда
            save_bot_state(dashboard_data)
            
            error_count = 0 
            time.sleep(15)  # Пауза между итерациями
            
        except RequestError as e:
            error_count += 1
            wait_time = min(10 * (2 ** error_count), 300)
            logger.error(f"Ошибка API Тинькофф: {e}. Повтор через {wait_time} сек...")
            time.sleep(wait_time)
        except Exception as e:
            logger.critical(f"Критическая ошибка в торговом цикле: {e}")
            time.sleep(30)
