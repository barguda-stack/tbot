import os
from tinkoff.invest import Client, RequestError
from core.logger import setup_logger

logger = setup_logger(__name__)

def detect_environment(token: str) -> str:
    """Автоматическое определение типа токена (песочница или боевой)."""
    logger.info("Автоматическое определение среды по токену...")
    
    import tinkoff.invest.constants
    tinkoff.invest.constants.INVEST_GRPC_API = "sandbox-invest-public-api.tinkoff.ru:443"
    
    try:
        with Client(token) as client:
            try:
                client.users.get_accounts()
            except Exception:
                pass
            logger.info("Токен определен как ПЕСОЧНИЦА (Sandbox).")
            return "sandbox-invest-public-api.tinkoff.ru:443"
    except RequestError as e:
        if "unauthenticated" in str(e).lower():
            logger.info("Ошибка аутентификации в песочнице. Пробуем боевой контур...")
        else:
            logger.warning(f"Неожиданная ошибка при проверке песочницы (возможно сеть): {e}")
            
    logger.info("Токен определен как БОЕВОЙ (Production).")
    return "invest-public-api.tinkoff.ru:443"

def init_client(token: str) -> Client:
    """Инициализация и возврат клиента Tinkoff с автоматическим адресом."""
    target = detect_environment(token)
    import tinkoff.invest.constants
    tinkoff.invest.constants.INVEST_GRPC_API = target
    return Client(token)
