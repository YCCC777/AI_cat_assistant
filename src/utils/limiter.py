import json
import os
from datetime import datetime
from src.utils.config import settings
from src.models.course import TokenUsage

class TokenLimiter:
    """
    負責每日 Token 消耗上限的控制與追蹤。
    """
    def __init__(self, storage_path: str = "token_usage.json"):
        self.storage_path = storage_path
        self._load_usage()

    def _load_usage(self) -> TokenUsage:
        """
        載入當前 Token 使用量資料。
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    usage = TokenUsage(**data)
                    # 檢查日期是否為今天
                    if usage.date == today:
                        self.usage = usage
                        return usage
            except Exception:
                pass
                
        # 初始化新的一天
        self.usage = TokenUsage(
            daily_limit=settings.DAILY_TOKEN_LIMIT,
            current_usage=0,
            date=today
        )
        self._save_usage()
        return self.usage

    def _save_usage(self):
        """
        儲存當前 Token 使用量資料。
        """
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.usage.model_dump(), f, ensure_ascii=False, indent=2)

    def is_limit_exceeded(self, estimated_usage: int = 100) -> bool:
        """
        檢查是否超出每日額度。
        """
        self._load_usage() # 同步一下日期與資料
        return self.usage.current_usage + estimated_usage > self.usage.daily_limit

    def add_usage(self, token_count: int):
        """
        累計消耗的 Token 量。
        """
        self.usage.current_usage += token_count
        self._save_usage()

    def get_remaining_capacity(self) -> int:
        """
        獲取剩餘可消耗額度。
        """
        return max(0, self.usage.daily_limit - self.usage.current_usage)

# 單例模式實例
token_limiter = TokenLimiter()
