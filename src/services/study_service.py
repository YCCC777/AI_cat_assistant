import logging
from datetime import datetime
from src.services.notion_service import notion_service
from src.services.line_service import line_service

logger = logging.getLogger(__name__)

class StudyService:
    """
    負責陪讀模組的業務邏輯。
    """
    
    def get_study_menu(self, user_id: str):
        """
        獲取陪讀主選單（目前先以文字回覆引導）。
        """
        progress = notion_service.get_user_progress(user_id)
        if not progress:
            return "喵～看來您還沒加入陪讀計畫呢！\n請輸入「報名 [考試名稱] [日期(YYYY-MM-DD)]」來啟動喵！\n例如：報名 iPAS AI 2026-05-20"
        
        return (
            f"🐾 您的陪讀進度 🐾\n"
            f"📖 目標：{progress['exam_name']}\n"
            f"⏳ 倒數：{self._calculate_countdown(progress['exam_date'])} 天\n"
            f"🍖 已讀：{progress['current_index']} 張學習卡\n\n"
            f"點擊下方選單或輸入「餵罐罐」來讀書喵！"
        )

    def get_setting_guide(self, user_id: str) -> str:
        """
        顯示陪讀設定引導訊息。
        """
        progress = notion_service.get_user_progress(user_id)
        if progress and progress.get("exam_name"):
            current = (
                f"目前本喵幫你追蹤的目標是【{progress['exam_name']}】，"
                f"考試日期 {progress['exam_date']}，"
                f"還有 {self._calculate_countdown(progress['exam_date'])} 天喵！\n\n"
                f"想換個新目標嗎？"
            )
        else:
            current = "喵～主人還沒有設定備考目標呢！讓本喵來幫你追蹤倒數和讀書進度吧！🐾"

        return (
            f"{current}\n\n"
            f"📝 設定方式：\n"
            f"輸入「報名 考試名稱 日期」\n\n"
            f"範例：\n"
            f"報名 iPAS AI應用規劃師 2026-05-20\n\n"
            f"設定完成後，每次捏肉球領學習卡時，本喵都會順便提醒你還剩幾天喵！🐾"
        )

    def register_exam(self, user_id: str, text: str):
        """
        解析報名資訊並存入 Notion。
        格式：報名 [考試名稱] [日期]
        """
        try:
            parts = text.replace("報名", "").strip().split()
            if len(parts) < 2:
                return "喵？格式不對喔！請輸入「報名 [考試名稱] [YYYY-MM-DD]」喵～"
            
            exam_name = parts[0]
            exam_date = parts[1]
            
            # 驗證日期格式
            datetime.strptime(exam_date, "%Y-%m-%d")
            
            success = notion_service.update_user_progress(user_id, {
                "exam_name": exam_name,
                "exam_date": exam_date,
                "current_index": 0
            })
            
            if success:
                return f"喵～收到！已經幫您記好目標「{exam_name}」了，考試日期是 {exam_date}。本喵會陪你一起努力的！🐾"
            else:
                return "喵嗚...存入進度時出了一點問題，請稍後再試喵～"
        except ValueError:
            return "喵？日期格式好像怪怪的，請使用 YYYY-MM-DD 格式（例如 2026-05-20）喵～"
        except Exception as e:
            logger.error(f"報名失敗: {str(e)}")
            return "喵嗚...報名出錯了，請找管理員救救本喵🐾"

    def send_next_card(self, reply_token: str, user_id: str):
        """
        發送下一張學習卡給使用者。
        """
        progress = notion_service.get_user_progress(user_id)
        if not progress:
            line_service.reply_text(reply_token, "喵？要先報名才能領罐罐（學習卡）喔！請輸入「報名」查看格式。")
            return

        current_index = progress["current_index"]
        next_index = current_index + 1
        
        card = notion_service.get_learning_card(next_index)
        if not card:
            line_service.reply_text(reply_token, "喵！恭喜您！目前的學習卡已經全部讀完了！本喵正在努力準備更多罐罐，請期待喔～🐾")
            return

        countdown_days = self._calculate_countdown(progress["exam_date"]) if progress.get("exam_date") else None
        line_service.reply_learning_card(reply_token, card["chapter"], card["content"], next_index, countdown_days)

    def handle_next_card_click(self, reply_token: str, user_id: str, finished_index: int):
        """
        處理使用者點擊「喵～我懂了」後的邏輯：更新進度並發送下一張。
        """
        # 1. 更新進度
        notion_service.update_user_progress(user_id, {"current_index": finished_index})
        
        # 2. 發送下一張
        self.send_next_card(reply_token, user_id)

    def get_countdown_msg(self, user_id: str):
        """
        獲取考試倒數訊息。
        """
        progress = notion_service.get_user_progress(user_id)
        if not progress or not progress["exam_date"]:
            return "喵？您還沒設定考試日期呢！請輸入「報名」來設定喵～"
        
        days = self._calculate_countdown(progress["exam_date"])
        if days < 0:
            return f"喵！考試已經過了 {-days} 天囉！辛苦了，給您揉揉肉球～🐾"
        elif days == 0:
            return "喵！！！就是今天！主人加油，本喵在這邊幫您集氣喵！🐾🔥"
        else:
            return f"距離【{progress['exam_name']}】還有 {days} 天喵！主人要持續餵食（讀書）喔，本喵會陪著你的！🐾"

    def _calculate_countdown(self, date_str: str) -> int:
        """
        計算日期差距。
        """
        if not date_str:
            return 0
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        return (target_date - today).days

# 單例模式實例
study_service = StudyService()
