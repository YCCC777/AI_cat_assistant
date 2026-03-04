import json
import os
from datetime import datetime
from src.utils.config import settings
import logging

logger = logging.getLogger(__name__)

class UserLimiter:
    """
    負責追蹤與限制單一使用者每日的解析次數，以及防止短時間內的頻繁請求。
    """
    def __init__(self, file_path="user_usage.json"):
        self.file_path = file_path
        self._ensure_file_exists()
        # 記憶體快取最後請求時間，不用存進檔案
        self.last_request_times = {}

    def is_too_fast(self, user_id: str, interval: int = 3) -> bool:
        """
        檢查使用者是否請求過於頻繁 (預設間隔 3 秒)。
        """
        # 管理員不限速
        if user_id == settings.ADMIN_LINE_USER_ID:
            return False
            
        now = datetime.now()
        last_time = self.last_request_times.get(user_id)
        
        if last_time and (now - last_time).total_seconds() < interval:
            return True
        
        # 更新最後請求時間
        self.last_request_times[user_id] = now
        return False

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({"date": str(datetime.now().date()), "users": {}}, f)

    def _get_data(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 如果日期不是今天，重設資料
            today = str(datetime.now().date())
            if data.get("date") != today:
                data = {"date": today, "users": {}}
                self._save_data(data)
            return data
        except Exception as e:
            logger.error(f"讀取使用者額度失敗: {str(e)}")
            return {"date": str(datetime.now().date()), "users": {}}

    def _save_data(self, data):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_limit_exceeded(self, user_id: str) -> bool:
        """
        檢查該使用者是否超過每日限額。管理員不限次數。
        """
        if user_id == settings.ADMIN_LINE_USER_ID:
            return False
            
        data = self._get_data()
        usage = data["users"].get(user_id, 0)
        return usage >= settings.USER_DAILY_LIMIT

    def add_usage(self, user_id: str):
        """
        增加使用次數。
        """
        if user_id == settings.ADMIN_LINE_USER_ID:
            return
            
        data = self._get_data()
        data["users"][user_id] = data["users"].get(user_id, 0) + 1
        self._save_data(data)

# 實例化
user_limiter = UserLimiter()
