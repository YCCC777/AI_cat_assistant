from notion_client import Client
import httpx
import json
import logging
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))
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
                    "last_check_in": props["Last_Check_In_Date"]["date"]["start"] if props.get("Last_Check_In_Date") and props["Last_Check_In_Date"]["date"] else None,
                    "streak_days": int(props["Streak_Days"]["number"] or 0) if props.get("Streak_Days") and props["Streak_Days"]["number"] is not None else 0,
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
            if data.get("clear_retry"):
                properties["Retry_Indices"] = {"rich_text": [{"text": {"content": "[]"}}]}
            if "check_in_date" in data:
                properties["Last_Check_In_Date"] = {"date": {"start": data["check_in_date"]}}
            if "streak_days" in data:
                properties["Streak_Days"] = {"number": data["streak_days"]}

            # 更新最後互動時間
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

    def get_learning_card(self, card_index: int, exam_type: str | None = None):
        """
        獲取指定索引的學習卡。
        exam_type 傳入時會加上 Exam_Type 過濾，避免初級/中級卡片混用。
        """
        if not self.notion or not self.card_db_id:
            return None

        try:
            conditions = [{"property": "Card_ID", "title": {"equals": str(card_index)}}]
            if exam_type:
                conditions.append({"property": "Exam_Type", "select": {"equals": exam_type}})
            query_filter = {"and": conditions} if len(conditions) > 1 else conditions[0]

            r = httpx.post(
                f"https://api.notion.com/v1/databases/{self.card_db_id}/query",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={"filter": query_filter},
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

    def get_latest_ai_news(self, limit: int = 5) -> list[dict]:
        """
        從 AI_News_Database 取最新 N 則 AI 週報資料。
        回傳 [{"content": str, "date": str}, ...] 依 News_Date 降序排列。
        """
        if not self.notion or not settings.NOTION_NEWS_DB_ID:
            return []
        try:
            r = httpx.post(
                f"https://api.notion.com/v1/databases/{settings.NOTION_NEWS_DB_ID}/query",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={
                    "sorts": [{"property": "News_Date", "direction": "descending"}],
                    "page_size": limit,
                },
                timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            news = []
            for item in results:
                props = item["properties"]
                content = props["News_Content"]["title"][0]["plain_text"] if props["News_Content"]["title"] else ""
                date = props["News_Date"]["date"]["start"] if props["News_Date"]["date"] else ""
                if content:
                    news.append({"content": content, "date": date})
            return news
        except Exception as e:
            logger.error(f"get_latest_ai_news 失敗: {str(e)}")
            return []

    def count_today_checkins(self) -> int:
        """
        查詢今日打卡人數（Last_Check_In_Date == today）。
        """
        if not self.notion or not self.user_db_id:
            return 0
        try:
            today_str = datetime.now(TW_TZ).date().isoformat()
            r = httpx.post(
                f"https://api.notion.com/v1/databases/{self.user_db_id}/query",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={"filter": {"property": "Last_Check_In_Date", "date": {"equals": today_str}}, "page_size": 100},
                timeout=15,
            )
            r.raise_for_status()
            return len(r.json().get("results", []))
        except Exception as e:
            logger.error(f"count_today_checkins 失敗: {str(e)}")
            return 0

    # ──────────────────────────────────────────────
    # 刷題系統（Quiz）
    # ──────────────────────────────────────────────

    def get_quiz_question(self, qid: str) -> dict | None:
        """以 Question_ID 取得一道刷題題目。"""
        if not self.notion or not settings.NOTION_QUIZ_DB_ID:
            return None
        try:
            r = httpx.post(
                f"https://api.notion.com/v1/databases/{settings.NOTION_QUIZ_DB_ID}/query",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={"filter": {"property": "Question_ID", "title": {"equals": qid}}},
                timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results")
            if results:
                return self._parse_quiz_question(results[0])
            return None
        except Exception as e:
            logger.error(f"get_quiz_question 失敗 qid={qid}: {e}")
            return None

    def get_all_quiz_question_ids(self, exam_type: str, subjects: list[str] | None = None) -> list[str]:
        """
        取得指定 exam_type 的所有 Question_ID（供組建 session pool 用）。
        subjects: 中級選考科目，e.g. ["科目一", "科目三"]；初級傳 None 不過濾科目。
        """
        if not self.notion or not settings.NOTION_QUIZ_DB_ID:
            return []
        try:
            # 建立 filter：初級只過濾 Exam_Type；中級再加 Subject OR 條件
            if subjects:
                base_filter = {
                    "and": [
                        {"property": "Exam_Type", "select": {"equals": exam_type}},
                        {"or": [
                            {"property": "Subject", "select": {"equals": s}} for s in subjects
                        ]},
                    ]
                }
            else:
                base_filter = {"property": "Exam_Type", "select": {"equals": exam_type}}

            ids = []
            cursor = None
            while True:
                body: dict = {"filter": base_filter, "page_size": 100}
                if cursor:
                    body["start_cursor"] = cursor
                r = httpx.post(
                    f"https://api.notion.com/v1/databases/{settings.NOTION_QUIZ_DB_ID}/query",
                    headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                    json=body,
                    timeout=20,
                )
                r.raise_for_status()
                data = r.json()
                for page in data.get("results", []):
                    title = page["properties"]["Question_ID"]["title"]
                    if title:
                        ids.append(title[0]["plain_text"])
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
            return ids
        except Exception as e:
            logger.error(f"get_all_quiz_question_ids 失敗: {e}")
            return []

    def get_random_quiz_question(self, exam_type: str, exclude_ids: list[str]) -> dict | None:
        """
        取一道隨機題目（Python-side random）。
        exam_type 過濾 + 排除 exclude_ids（已答過的）。
        如果所有題都答過，直接回傳 None（由呼叫端決定是否 reset）。
        """
        if not self.notion or not settings.NOTION_QUIZ_DB_ID:
            return None
        try:
            all_questions = []
            cursor = None
            while True:
                body: dict = {
                    "filter": {"property": "Exam_Type", "select": {"equals": exam_type}},
                    "page_size": 100,
                }
                if cursor:
                    body["start_cursor"] = cursor
                r = httpx.post(
                    f"https://api.notion.com/v1/databases/{settings.NOTION_QUIZ_DB_ID}/query",
                    headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                    json=body,
                    timeout=20,
                )
                r.raise_for_status()
                data = r.json()
                all_questions.extend(data.get("results", []))
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")

            exclude_set = set(exclude_ids)
            pool = [q for q in all_questions
                    if q["properties"]["Question_ID"]["title"][0]["plain_text"] not in exclude_set]
            if not pool:
                return None
            import random
            return self._parse_quiz_question(random.choice(pool))
        except Exception as e:
            logger.error(f"get_random_quiz_question 失敗: {e}")
            return None

    def _parse_quiz_question(self, page: dict) -> dict:
        """從 Notion page dict 解析成 quiz question dict。"""
        p = page["properties"]
        def rt(field): return p[field]["rich_text"][0]["text"]["content"] if p.get(field, {}).get("rich_text") else ""
        def sel(field): return p[field]["select"]["name"] if p.get(field, {}).get("select") else ""
        return {
            "qid":            p["Question_ID"]["title"][0]["plain_text"] if p["Question_ID"]["title"] else "",
            "exam_type":      sel("Exam_Type"),
            "chapter":        rt("Chapter"),
            "source":         sel("Source"),
            "question":       rt("Question"),
            "option_a":       rt("Option_A"),
            "option_b":       rt("Option_B"),
            "option_c":       rt("Option_C"),
            "option_d":       rt("Option_D"),
            "correct_answer": sel("Correct_Answer"),
            "explanation":    rt("Explanation"),
        }

    def get_quiz_progress(self, user_id: str, exam_type: str = "") -> dict | None:
        """取得用戶的刷題進度（按 User_ID + Exam_Type 隔離初級與中級）。"""
        if not self.notion or not settings.NOTION_QUIZ_PROGRESS_DB_ID:
            return None
        try:
            if exam_type:
                query_filter = {
                    "and": [
                        {"property": "User_ID",   "title":     {"equals": user_id}},
                        {"property": "Exam_Type", "rich_text": {"equals": exam_type}},
                    ]
                }
            else:
                query_filter = {"property": "User_ID", "title": {"equals": user_id}}

            r = httpx.post(
                f"https://api.notion.com/v1/databases/{settings.NOTION_QUIZ_PROGRESS_DB_ID}/query",
                headers={"Authorization": f"Bearer {settings.NOTION_TOKEN}", "Notion-Version": NOTION_VERSION},
                json={"filter": query_filter},
                timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results")
            if results:
                p = results[0]["properties"]
                def rt(field): return p[field]["rich_text"][0]["text"]["content"] if p.get(field, {}).get("rich_text") else ""
                wrong_raw = rt("Wrong_Queue")
                answered_raw = rt("Answered_IDs")
                subjects_raw = rt("Selected_Subjects")   # 中級選考科目，初級為空
                return {
                    "page_id":          results[0]["id"],
                    "total_answered":   int(p["Total_Answered"]["number"] or 0) if p.get("Total_Answered") else 0,
                    "correct_count":    int(p["Correct_Count"]["number"] or 0) if p.get("Correct_Count") else 0,
                    "wrong_queue":      json.loads(wrong_raw) if wrong_raw else [],
                    "answered_ids":     json.loads(answered_raw) if answered_raw else [],
                    "selected_subjects": json.loads(subjects_raw) if subjects_raw else [],  # 中級用
                }
            return None
        except Exception as e:
            logger.error(f"get_quiz_progress 失敗: {e}")
            return None

    def update_quiz_progress(self, user_id: str, data: dict, exam_type: str = "") -> bool:
        """
        更新或建立用戶刷題進度（按 exam_type 隔離）。
        支援 keys：
          increment_total, increment_correct,
          add_answered, reset_answered,
          add_wrong_queue, remove_wrong_queue
        """
        if not self.notion or not settings.NOTION_QUIZ_PROGRESS_DB_ID:
            return False
        try:
            progress = self.get_quiz_progress(user_id, exam_type=exam_type)
            props: dict = {}

            total = progress["total_answered"] if progress else 0
            correct = progress["correct_count"] if progress else 0
            wrong_q: list = list(progress["wrong_queue"]) if progress else []
            answered: list = list(progress["answered_ids"]) if progress else []

            if data.get("increment_total"):
                props["Total_Answered"] = {"number": total + 1}
            if data.get("increment_correct"):
                props["Correct_Count"] = {"number": correct + 1}
            if "add_answered" in data:
                qid = data["add_answered"]
                if qid not in answered:
                    answered.append(qid)
                props["Answered_IDs"] = {"rich_text": [{"text": {"content": json.dumps(answered)}}]}
            if data.get("reset_answered"):
                props["Answered_IDs"] = {"rich_text": [{"text": {"content": "[]"}}]}
            if "add_wrong_queue" in data:
                qid = data["add_wrong_queue"]
                if qid not in wrong_q and len(wrong_q) < 20:
                    wrong_q.append(qid)
                props["Wrong_Queue"] = {"rich_text": [{"text": {"content": json.dumps(wrong_q)}}]}
            if "remove_wrong_queue" in data:
                qid = data["remove_wrong_queue"]
                wrong_q = [q for q in wrong_q if q != qid]
                props["Wrong_Queue"] = {"rich_text": [{"text": {"content": json.dumps(wrong_q)}}]}

            if not props:
                return True

            if progress:
                self.notion.pages.update(page_id=progress["page_id"], properties=props)
            else:
                props["User_ID"]   = {"title":     [{"text": {"content": user_id}}]}
                props["Exam_Type"] = {"rich_text": [{"text": {"content": exam_type}}]}
                self.notion.pages.create(
                    parent={"database_id": settings.NOTION_QUIZ_PROGRESS_DB_ID},
                    properties=props,
                )
            return True
        except Exception as e:
            logger.error(f"update_quiz_progress 失敗: {e}")
            return False

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
