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

        # 這裡使用 AI 給出的 iso_start_time / iso_end_time 
        # 如果解析不出來，則預設 2026-03-21 作為保底
        start_time = course.iso_start_time or '2026-03-21T09:00:00'
        end_time = course.iso_end_time or '2026-03-21T11:00:00'

        event = {
            'summary': f'📚 {course.name}',
            'location': course.location_url or '線上',
            'description': f'主辦單位: {course.organizer or "未知"}\n\n原始訊息:\n{course.raw_content}',
            'start': {
                'dateTime': start_time,
                'timeZone': 'Asia/Taipei',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Asia/Taipei',
            },
        }

        try:
            event = self.service.events().insert(
                calendarId=settings.GOOGLE_CALENDAR_ID, body=event
            ).execute()
            logger.info(f"成功新增行事曆事件: {event.get('htmlLink')}")
            return event
        except Exception as e:
            logger.error(f"新增行事曆事件失敗: {str(e)}")
            return None

# 單例模式實例
calendar_service = CalendarService()
