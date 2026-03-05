from google import genai
import json
from typing import List, Union
from src.utils.config import settings
from src.models.course import CourseInfo


class GeminiService:
    """
    負責 AI 解析與過濾的核心服務。
    """
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def parse_course_info(self, message_content: str) -> Union[CourseInfo, List[CourseInfo]]:
        """
        將 LINE 轉傳的內容解析為課程資訊，支援一次多個課程。
        """
        prompt = f"""
你是一個可愛、溫暖的「貓咪助手」，對話請使用道地的台灣繁體中文，並帶有「喵～」的語氣與 Emoji 表情符號。
你的任務是解析以下 LINE 社群轉傳的訊息，判斷是否為「免費 AI 相關課程資訊」。

訊息內容如下：
---
{message_content}
---

請按照以下規則執行：
1. **核心抓取**：精準解析「課程名稱」、「時間（日期與時刻）」、「報名/線上會議連結（Google Meet, Zoom, KKTIX, Facebook 活動等）」、「講師或主辦單位」。
2. **格式轉換**：將課程時間轉換為 ISO 8601 格式（YYYY-MM-DDTHH:MM:SS）。
   - 如果年份不明，預設為 2026 年。
   - 如果沒有明確結束時間，預設課程長度為 120 分鐘。
   - 時區統一設為台北時間（+08:00）。
3. **判定準則**：
   - 只要包含「課程」、「講座」、「研討會」、「直播分享」等具有明確「時間點」的資訊，即視為有效課程。
   - 如果只是單純的新聞連結或 YouTube 影片（無具體活動時間），則將 `is_course` 標記為 false，並在 `reason` 說明原因。
4. **多重解析**：如果訊息中包含多個不同的課程資訊，請回傳 JSON 列表 (List of Objects)；如果只有一個，回傳單個物件。

請回覆純 JSON 格式的資料，格式如下：
{{
  "name": "課程名稱",
  "date_time": "原始顯示日期與時間",
  "iso_start_time": "2026-03-15T14:00:00",
  "iso_end_time": "2026-03-15T16:00:00",
  "location_url": "會議連結或報名網址",
  "organizer": "主辦單位或講師",
  "raw_content": "完整原始訊息",
  "is_course": true/false,
  "reason": "說明解析結果"
}}
"""
        try:
            response = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL_NAME,
                contents=prompt
            )
            json_text = response.text.strip()
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0].strip()

            data = json.loads(json_text)

            if isinstance(data, list):
                return [CourseInfo(**item) for item in data]
            else:
                return CourseInfo(**data)
        except Exception as e:
            raise e


# 單例模式實例
gemini_service = GeminiService()
