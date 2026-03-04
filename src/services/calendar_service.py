from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import json
import logging
from src.utils.config import settings
from src.models.course import CourseInfo

logger = logging.getLogger(__name__)

class CalendarService:
    """
    負責與 Google Calendar API 互動。
    """
    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.service = self._authenticate()

    def _authenticate(self):
        """
        驗證 Google Service Account。支援檔案與環境變數內容讀取。
        """
        try:
            creds = None
            # 優先從環境變數讀取 JSON 內容 (Hugging Face 模式)
            if settings.GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT:
                logger.info("📅 正在從環境變數讀取 Google 憑證...")
                service_account_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT)
                creds = service_account.Credentials.from_service_account_info(
                    service_account_info, scopes=self.scopes
                )
            # 次之從本地檔案讀取 (開發模式)
            elif os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_JSON):
                logger.info(f"📅 正在從檔案讀取 Google 憑證: {settings.GOOGLE_SERVICE_ACCOUNT_JSON}")
                creds = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=self.scopes
                )
            else:
                logger.warning("❌ 找不到 Google 憑證資訊，跳過行事曆功能。")
                return None

            if creds:
                logger.info(f"🔑 正在使用服務帳號：{creds.service_account_email}")
                logger.info(f"📅 嘗試連接日曆 ID：[{settings.GOOGLE_CALENDAR_ID}]")
                return build('calendar', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Google 驗證失敗: {str(e)}")
            return None

    def add_event(self, course: CourseInfo):
        """
        新增課程至 Google 行事曆。
        """
        if not self.service:
            logger.info("行事曆服務未初始化，略過新增。")
            return None

        # 1. 時間格式處理：確保符合 ISO 8601 並包含時區
        # 如果 AI 沒給，保底設為 2026-03-21
        start_time = course.iso_start_time or '2026-03-21T09:00:00'
        end_time = course.iso_end_time or '2026-03-21T11:00:00'

        # 確保格式中包含時區資訊 (若無則加上 +08:00)
        def ensure_timezone(dt_str):
            if "+" not in dt_str and "Z" not in dt_str:
                return f"{dt_str}+08:00"
            return dt_str

        start_dt = ensure_timezone(start_time)
        end_dt = ensure_timezone(end_time)

        event = {
            'summary': f'📚 {course.name}',
            'location': course.location_url or '線上',
            'description': f'主辦單位: {course.organizer or "未知"}\n\n原始訊息:\n{course.raw_content}',
            'start': {
                'dateTime': start_dt,
            },
            'end': {
                'dateTime': end_dt,
            },
        }

        try:
            logger.info(f"正在嘗試新增行事曆事件: {course.name} ({start_dt})")
            event_result = self.service.events().insert(
                calendarId=settings.GOOGLE_CALENDAR_ID, body=event
            ).execute()
            logger.info(f"成功新增行事曆事件: {event_result.get('htmlLink')}")
            return event_result
        except Exception as e:
            logger.error(f"新增行事曆事件失敗! 詳細錯誤: {str(e)}")
            # 拋出部分錯誤細節以便上層追蹤，但不中斷整體流程
            return None

# 單例模式實例
calendar_service = CalendarService()
