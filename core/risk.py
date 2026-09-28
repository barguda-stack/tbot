import os
from core.logger import setup_logger

logger = setup_logger(__name__)

KILL_SWITCH_FILE = "kill_switch.flag"

class RiskManager:
    def __init__(self, max_drawdown_percent: float = 2.0):
        self.max_drawdown_percent = max_drawdown_percent
        self.initial_balance = None
    
    def check_kill_switch(self) -> bool:
        """Проверяет наличие файла аварийной остановки."""
        if os.path.exists(KILL_SWITCH_FILE):
            logger.critical("ВНИМАНИЕ! Активирован Kill Switch (аварийная остановка). Бот приостанавливает торговлю!")
            return True
        return False
        
    def evaluate_risk(self, current_balance: float) -> bool:
        """Проверяет просадку общего баланса. Если превышает лимит - активирует Kill Switch."""
        if self.initial_balance is None:
            self.initial_balance = current_balance
            return True
            
        drawdown = ((self.initial_balance - current_balance) / self.initial_balance) * 100
        if drawdown >= self.max_drawdown_percent:
            logger.critical(f"Превышен лимит просадки: {drawdown:.2f}% (Макс: {self.max_drawdown_percent}%). Активация программного Kill Switch!")
            with open(KILL_SWITCH_FILE, 'w') as f:
                f.write("Drawdown limit exceeded")
            return False
        return True
