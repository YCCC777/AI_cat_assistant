from notion_client import Client
import httpx
import logging
from src.utils.config import settings
from src.models.course import CourseInfo

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"

class NotionService:
    """
    負責與 Notion API 互動，作為課程資料庫。
    """
    def __init__(self):
        # 初始化 Notion 用戶端
        if settings.NOTION_TOKEN:
            self.notion = Client(auth=settings.NOTION_TOKEN)
            self.course_db_id = settings.NOTION_DATABASE_ID
            self.user_db_id = settings.NOTION_USER_PROGRESS_DB_ID
            self.card_db_id = settings.NOTION_LEARNING_CARD_DB_ID
        else:
            self.notion = None
            logger.warning("Notion Token 缺失，跳過 Notion 功能。")

    def add_course(self, course: CourseInfo):
        """
        將課程資訊新增至 Notion 資料庫。
        """
        if not self.notion or not self.course_db_id:
            return None

        try:
            # 依照 Notion 資料庫屬性設計 (範例)
            new_page = {
                "parent": {"database_id": self.course_db_id},
                "properties": {
                    "課程名稱": {
                        "title": [{"text": {"content": course.name}}]
                    },
                    "日期與時間": {
                        "rich_text": [{"text": {"content": course.date_time}}]
                    },
                    "連結": {
                        "url": course.location_url if course.location_url else None
                    },
                    "主辦單位": {
                        "rich_text": [{"text": {"content": course.organizer or "無"}}]
                    },
                    "備註": {
                        "rich_text": [{"text": {"content": course.raw_content[:2000]}}] # 避免超限
                    }
                }
            }
            response = self.notion.pages.create(**new_page)
            logger.info("成功同步至 Notion。")
            return response
        except Exception as e:
            logger.error(f"同步 Notion 失敗: {str(e)}")
            return None

    def get_user_progress(self, user_id: str):
        """
        獲取使用者在 Notion 中的進度。
        """
        if not self.notion or not self.user_db_id:
            return None

        try:
            r = httpx.post(
                f"https://api.notion.com/v1/databases/{self.user_db_id}/query",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={"filter": {"property": "User_ID", "title": {"equals": user_id}}},
                timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results")
            if results:
                props = results[0]["properties"]
                return {
                    "page_id": results[0]["id"],
                    "exam_name": props["Exam_Name"]["rich_text"][0]["text"]["content"] if props["Exam_Name"]["rich_text"] else "未設定",
                    "exam_date": props["Exam_Date"]["date"]["start"] if props["Exam_Date"]["date"] else None,
                    "current_index": props["Current_Card_Index"]["number"] or 0
                }
            return None
        except Exception as e:
            logger.error(f"獲取使用者進度失敗: {str(e)}")
            return None

    def update_user_progress(self, user_id: str, data: dict):
        """
        更新或建立使用者的進度。
        """
        if not self.notion or not self.user_db_id:
            return None

        try:
            # 先檢查使用者是否已存在
            progress = self.get_user_progress(user_id)
            
            # 構建 properties
            properties = {}
            if "exam_name" in data:
                properties["Exam_Name"] = {"rich_text": [{"text": {"content": data["exam_name"]}}]}
            if "exam_date" in data:
                properties["Exam_Date"] = {"date": {"start": data["exam_date"]}}
            if "current_index" in data:
                properties["Current_Card_Index"] = {"number": data["current_index"]}
            
            # 更新最後互動時間
            from datetime import datetime
            properties["Last_Interaction"] = {"date": {"start": datetime.now().isoformat()}}

            if progress:
                # 更新現有頁面
                self.notion.pages.update(page_id=progress["page_id"], properties=properties)
            else:
                # 建立新頁面
                properties["User_ID"] = {"title": [{"text": {"content": user_id}}]}
                self.notion.pages.create(parent={"database_id": self.user_db_id}, properties=properties)
            
            return True
        except Exception as e:
            logger.error(f"更新使用者進度失敗: {str(e)}")
            return False

    def get_learning_card(self, card_index: int):
        """
        獲取指定索引的學習卡。
        """
        if not self.notion or not self.card_db_id:
            return None

        try:
            r = httpx.post(
                f"https://api.notion.com/v1/databases/{self.card_db_id}/query",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={"filter": {"property": "Card_ID", "number": {"equals": int(card_index)}}},
                timeout=15,
            )
            if not r.is_success:
                logger.error(f"獲取學習卡 400 詳情: {r.text}")
            r.raise_for_status()
            results = r.json().get("results")
            if results:
                props = results[0]["properties"]
                return {
                    "chapter": props["Chapter"]["rich_text"][0]["text"]["content"] if props["Chapter"]["rich_text"] else "通用",
                    "content": props["Content"]["rich_text"][0]["text"]["content"] if props["Content"]["rich_text"] else ""
                }
            return None
        except Exception as e:
            logger.error(f"獲取學習卡失敗: {str(e)}")
            return None

# 單例模式實例
notion_service = NotionService()
