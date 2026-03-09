from notion_client import Client
import httpx
import json
import logging
from src.utils.config import settings
from src.models.course import CourseInfo

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"


def _extract_short_content(content: str, max_len: int = 180) -> str:
    """從 Content 萃取 ⚠️ 考試陷阱段落，控制在 max_len 字內。若無陷阱段則取前兩條 bullet。"""
    lines = [l.strip() for l in content.replace("<br>", "\n").split("\n") if l.strip()]
    trap_lines = []
    in_trap = False
    for line in lines:
        if "⚠️" in line:
            in_trap = True
        if in_trap:
            trap_lines.append(line)
    if trap_lines:
        return "\n".join(trap_lines)[:max_len]
    bullets = [l for l in lines if l.startswith("•")]
    if bullets:
        return "\n".join(bullets[:2])[:max_len]
    return content[:max_len]

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
            self.report_db_id = settings.NOTION_REPORT_DB_ID
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
                    "current_index": props["Current_Card_Index"]["number"] or 0,
                    "understood_count": int(props["Understood_Count"]["number"] or 0) if props.get("Understood_Count") and props["Understood_Count"]["number"] is not None else 0,
                    "not_sure_count": int(props["Not_Sure_Count"]["number"] or 0) if props.get("Not_Sure_Count") and props["Not_Sure_Count"]["number"] is not None else 0,
                    "retry_indices": json.loads(props["Retry_Indices"]["rich_text"][0]["text"]["content"]) if props.get("Retry_Indices") and props["Retry_Indices"]["rich_text"] else [],
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
            if "increment_understood" in data:
                cur = progress["understood_count"] if progress else 0
                properties["Understood_Count"] = {"number": cur + 1}
            if "increment_not_sure" in data:
                cur = progress["not_sure_count"] if progress else 0
                properties["Not_Sure_Count"] = {"number": cur + 1}
            if "add_retry" in data:
                cur_retry = list(progress["retry_indices"]) if progress else []
                if data["add_retry"] not in cur_retry:
                    cur_retry.append(data["add_retry"])
                properties["Retry_Indices"] = {"rich_text": [{"text": {"content": json.dumps(cur_retry)}}]}
            if "remove_retry" in data:
                cur_retry = list(progress["retry_indices"]) if progress else []
                cur_retry = [i for i in cur_retry if i != data["remove_retry"]]
                properties["Retry_Indices"] = {"rich_text": [{"text": {"content": json.dumps(cur_retry)}}]}

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
                json={"filter": {"property": "Card_ID", "title": {"equals": str(card_index)}}},
                timeout=15,
            )
            if not r.is_success:
                logger.error(f"獲取學習卡 400 詳情: {r.text}")
            r.raise_for_status()
            results = r.json().get("results")
            if results:
                props = results[0]["properties"]
                content = props["Content"]["rich_text"][0]["text"]["content"] if props["Content"]["rich_text"] else ""
                chapter = props["Chapter"]["rich_text"][0]["text"]["content"] if props["Chapter"]["rich_text"] else "通用"
                question = props["Question"]["rich_text"][0]["text"]["content"] if props.get("Question", {}).get("rich_text") else ""
                # P2: 動態計算 short_content 上限，使答題訊息「【chapter】\n\n{short_content}」≤ 200 字
                answer_overhead = len(chapter) + 5  # 【 + chapter + 】 + \n\n
                max_short = max(60, 200 - answer_overhead)
                return {
                    "chapter": chapter,
                    "content": content,
                    "short_content": _extract_short_content(content, max_len=max_short),
                    "question": question,
                }
            return None
        except Exception as e:
            logger.error(f"獲取學習卡失敗: {str(e)}")
            return None

    def create_card_report(self, card_id: int, reporter_id: str, content: str) -> bool:
        if not self.notion or not self.report_db_id:
            return False
        try:
            r = httpx.post(
                f"https://api.notion.com/v1/pages",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={
                    "parent": {"database_id": self.report_db_id},
                    "properties": {
                        "Card_ID": {"title": [{"text": {"content": str(card_id)}}]},
                        "Reporter_ID": {"rich_text": [{"text": {"content": reporter_id}}]},
                        "Content": {"rich_text": [{"text": {"content": content}}]},
                        "Status": {"select": {"name": "待處理"}},
                    }
                },
                timeout=15,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"建立錯誤回報失敗: {str(e)}")
            return False


# 單例模式實例
notion_service = NotionService()
