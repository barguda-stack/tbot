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
    
    error_count = 0
    
    while True:
        try:
            # 1. Проверка аварийной остановки (Kill Switch)
            if risk_manager.check_kill_switch():
                time.sleep(30)
                continue
            
            # Читаем пользовательские настройки из UI
            from core.storage import get_settings, save_settings
            settings = get_settings()
            
            # 2. Общий риск-менеджмент
            balance = market.get_account_balance(client, account_id)
            if not risk_manager.evaluate_risk(balance):
                time.sleep(30)
                continue
            
            # 3. Получение открытых позиций
            open_positions = market.get_open_positions(client, account_id)
            
            dashboard_data = {
                "timestamp": time.time(),
                "balance": balance,
                "instruments": []
            }
            
            instruments_settings = settings.get("instruments", {})
            settings_changed = False
            
            # 4. Анализ каждого инструмента из добавленных в настройки
            for ticker, inst_settings in instruments_settings.items():
                figi = inst_settings.get("figi")
                if not figi:
                    continue
                    
                is_active = inst_settings.get("active", False)
                max_lots = inst_settings.get("max_lots", 1)
                max_trades = inst_settings.get("max_trades", 5)
                ml_trained = inst_settings.get("ml_trained", False)
                
                # Если инструмент не обучен, запускаем сбор истории и обучение
                if not ml_trained:
                    logger.info(f"[{ticker}] Инструмент не обучен. Запуск сбора истории...")
                    historical_data = market.get_historical_data_1y(client, figi)
                    if historical_data:
                        # Запуск обучения
                        success = strategy.train_30_algorithms(ticker, historical_data)
                        if success:
                            # Помечаем инструмент как обученный
                            settings["instruments"][ticker]["ml_trained"] = True
                            ml_trained = True
                            settings_changed = True
                    else:
                        logger.warning(f"[{ticker}] Не удалось собрать исторические данные для обучения.")
                
                # Рыночные данные
                current_price = market.get_price(client, figi)
                candles_data = market.get_candles_15m_1d(client, figi)
                position_balance = open_positions.get(figi, 0)
                invested_amount = position_balance * current_price * inst["lot"]
                
                # Подготовка данных для UI
                dashboard_data["instruments"].append({
                    "figi": figi,
                    "ticker": ticker,
                    "name": inst_settings.get("name", ticker),
                    "lot": inst_settings.get("lot", 1),
                    "current_price": current_price,
                    "invested": invested_amount,
                    "position": position_balance,
                    "active": is_active,
                    "max_lots": max_lots,
                    "max_trades": max_trades,
                    "ml_trained": ml_trained,
                    "candles": candles_data
                })
                
                # 5. Принятие решений (если инструмент разрешен к торгам)
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
            
            if settings_changed:
                save_settings(settings)
                
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
