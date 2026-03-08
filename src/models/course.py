from pydantic import BaseModel, Field
from typing import Optional, List

class CourseInfo(BaseModel):
    """
    從 LINE 訊息中解析出的課程資訊模型。
    """
    name: Optional[str] = Field(None, description="課程名稱")
    date_time: Optional[str] = Field(None, description="課程時間（包含日期與具體時刻）")
    location_url: Optional[str] = Field(None, description="報名連結、Google Meet 或 Zoom 等會議連結")
    organizer: Optional[str] = Field(None, description="主辦單位或講師名稱")
    raw_content: Optional[str] = Field(None, description="原始完整訊息內容，用於存入行事曆備註")
    iso_start_time: Optional[str] = Field(None, description="符合 ISO 8601 格式的課程開始時間 (YYYY-MM-DDTHH:MM:SS)")
    iso_end_time: Optional[str] = Field(None, description="符合 ISO 8601 格式的課程結束時間 (預設開始後 2 小時)")
    is_course: bool = Field(True, description="是否為有效的免費 AI 課程資訊")
    reason: Optional[str] = Field(None, description="如果不是課程，記錄原因（例如：YT 影片、一般新聞）")

class TokenUsage(BaseModel):
    """
    用於記錄當日 Token 消耗情況。
    """
    daily_limit: int = 50000
    current_usage: int = 0
    date: str # 格式: YYYY-MM-DD
