import logging
from datetime import datetime
from src.services.notion_service import notion_service
from src.services.line_service import line_service
from src.utils.exam_dates import get_exam_dates, get_all_exam_names

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
        
        understood = progress.get("understood_count", 0)
        retry_count = len(progress.get("retry_indices", []))
        total_answered = progress.get("understood_count", 0) + progress.get("not_sure_count", 0)
        accuracy = int(understood / total_answered * 100) if total_answered > 0 else 0
        retry_hint = f"\n🔁 複習佇列：{retry_count} 張（下次捏肉球優先出現）" if retry_count > 0 else ""
        return (
            f"🐾 您的陪讀進度 🐾\n"
            f"📖 目標：{progress['exam_name']}\n"
            f"⏳ 倒數：{self._calculate_countdown(progress['exam_date'])} 天\n"
            f"🍖 已讀：{progress['current_index']} 張學習卡\n"
            f"✅ 已懂：{understood} 張\n"
            f"📊 答對率：{accuracy}%"
            f"{retry_hint}\n\n"
            f"點擊下方選單或輸入「捏肉球」來讀書喵！"
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
            f"報名 iPAS AI應用規劃師（初級） 2026-05-20\n\n"
            f"⚠️ 目前僅支援 iPAS 初級\n\n"
            f"設定完成後，每次捏肉球領學習卡時，本喵都會順便提醒你還剩幾天喵！🐾"
        )

    def register_exam(self, user_id: str, text: str):
        """
        解析報名資訊並存入 Notion。
        格式：報名 [考試名稱] [日期]（日期一定是最後一格）
        僅接受 iPAS AI應用規劃師（初級）。
        """
        try:
            parts = text.replace("報名", "").strip().split()
            if len(parts) < 2:
                return "喵？格式不對喔！請輸入「報名 考試名稱 YYYY-MM-DD」喵～\n例如：報名 iPAS AI應用規劃師（初級） 2026-05-20"

            exam_date = parts[-1]
            exam_name = " ".join(parts[:-1])

            # 驗證日期格式
            datetime.strptime(exam_date, "%Y-%m-%d")

            # 僅接受支援的考試名稱
            supported = get_all_exam_names()
            is_supported = any(name in exam_name for name in supported)
            if not is_supported:
                return (
                    "喵嗚...本喵目前只支援 iPAS AI應用規劃師（初級）的陪讀計畫喔！🐾\n"
                    "請點選「陪讀設定」使用選單來報名，或輸入正確考試名稱喵～"
                )

            if "中級" in exam_name:
                return "喵嗚...本喵目前只支援 iPAS AI應用規劃師（初級），中級還在努力準備中，請主人稍待喵！🐾"
            if "初級" not in exam_name:
                return "喵～請在考試名稱中註明「初級」或「中級」，例如：\n報名 iPAS AI應用規劃師（初級） 2026-05-20"

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

    def register_exam_direct(self, user_id: str, exam_name: str, exam_date: str) -> str:
        """
        直接用考試名稱 + 日期完成報名（供 Postback 兩層選單使用）。
        """
        try:
            success = notion_service.update_user_progress(user_id, {
                "exam_name": exam_name,
                "exam_date": exam_date,
                "current_index": 0
            })
            if success:
                return f"喵～收到！已幫您記好目標「{exam_name}」，考試日期 {exam_date}。本喵會陪你一起努力的！🐾"
            else:
                return "喵嗚...存入進度時出了一點問題，請稍後再試喵～"
        except Exception as e:
            logger.error(f"register_exam_direct 失敗: {str(e)}")
            return "喵嗚...報名出錯了，請找管理員救救本喵🐾"

    def get_exam_type_options(self) -> list[tuple[str, str, str]]:
        """
        回傳考試種類的 Postback Quick Reply 選項。
        格式：[(label, postback_data, display_text), ...]
        """
        options = []
        for exam_name in get_all_exam_names():
            # label 限 20 字
            label = "iPAS AI應用規劃師(初級)"
            data = f"action=show_exam_dates&exam={exam_name}"
            display = f"我要報名 {exam_name}"
            options.append((label, data, display))
        return options

    def get_exam_date_options(self, exam_name: str) -> list[tuple[str, str, str]]:
        """
        回傳指定考試的日期 Postback Quick Reply 選項。
        格式：[(label, postback_data, display_text), ...]
        """
        dates = get_exam_dates(exam_name)
        options = []
        for label, iso_date in dates:
            data = f"action=register_exam&exam={exam_name}&date={iso_date}"
            display = f"報名 {label}"
            # Quick Reply label 最多 20 字
            options.append((label[:20], data, display))
        return options

    def handle_pinch_paw(self, reply_token: str, user_id: str):
        """
        捏肉球統一入口。
        今天第一次：打卡（更新連續天數）→ 回傳打卡訊息 + Quick Reply 按鈕「翻開今日學習卡」。
        今天已打卡：直接發學習卡。
        """
        progress = notion_service.get_user_progress(user_id)
        if not progress:
            line_service.reply_text(reply_token, "喵？要先設定考試目標才能捏肉球喔！請點選「陪讀設定」或輸入「陪讀設定」查看格式。")
            return

        today_str = datetime.now().date().isoformat()
        last_check_in = progress.get("last_check_in")
        # Notion date 有時會帶時區，取前 10 字元確保只比較日期
        last_check_in_date = (last_check_in or "")[:10]

        if last_check_in_date == today_str:
            # 今天已打卡，直接發學習卡
            self.send_next_card(reply_token, user_id)
            return

        # 計算連續天數
        streak = progress.get("streak_days", 0)
        if last_check_in_date:
            last_date = datetime.strptime(last_check_in_date, "%Y-%m-%d").date()
            diff = (datetime.now().date() - last_date).days
            streak = streak + 1 if diff == 1 else 1
        else:
            streak = 1

        # 更新打卡記錄；若失敗仍繼續，避免用戶卡在打卡畫面
        ok = notion_service.update_user_progress(user_id, {
            "check_in_date": today_str,
            "streak_days": streak,
        })
        if not ok:
            logger.warning(f"打卡記錄寫入失敗 user={user_id[:8]}，直接發學習卡")
            self.send_next_card(reply_token, user_id)
            return

        # 回傳打卡訊息
        countdown = self._calculate_countdown(progress["exam_date"]) if progress.get("exam_date") else None
        exam_name = progress.get("exam_name") if progress.get("exam_name") != "未設定" else None
        line_service.reply_check_in(reply_token, streak, exam_name, countdown)

    def send_next_card(self, reply_token: str, user_id: str, skip_retry: bool = False):
        """
        翻牌第一步：優先發送複習佇列中的卡，佇列空時才推進到下一張新卡。
        skip_retry=True 時強制走新卡邏輯（current_index + 1），忽略 retry 佇列。
        """
        progress = notion_service.get_user_progress(user_id)
        if not progress:
            line_service.reply_text(reply_token, "喵？要先設定考試目標才能捏肉球喔！請點選「陪讀設定」或輸入「陪讀設定」查看格式。")
            return

        # P3：優先取複習佇列（除非明確要求跳過）
        retry_indices = progress.get("retry_indices", [])
        if retry_indices and not skip_retry:
            card_index = retry_indices[0]
            is_retry = True
        else:
            card_index = progress["current_index"] + 1
            is_retry = False

        exam_type = self._derive_exam_type(progress.get("exam_name", ""))
        card = notion_service.get_learning_card(card_index, exam_type)
        if not card:
            line_service.reply_all_cards_done(reply_token)
            return

        line_service.reply_card_question(reply_token, card["chapter"], card_index, card.get("question", ""), is_retry=is_retry)

    def handle_reveal_card(self, reply_token: str, card_index: int, is_retry: bool = False):
        """
        翻牌第二步：使用者點「看解答」後，顯示考試陷阱精華 + 自評按鈕。
        """
        card = notion_service.get_learning_card(card_index)
        if not card:
            line_service.reply_text(reply_token, "喵嗚...找不到這張學習卡，請稍後再試喵～🐾")
            return
        full_text = card["content"].replace("<br>", "\n")
        line_service.reply_card_answer(reply_token, card["chapter"], full_text, card_index, is_retry=is_retry)

    def handle_card_understood(self, reply_token: str, user_id: str, card_index: int, is_retry: bool = False):
        """
        使用者點「✅ 懂了」：
        - 複習卡：從 retry_indices 移除，不推進 current_index
        - 新卡：推進 current_index
        """
        if is_retry:
            notion_service.update_user_progress(user_id, {"remove_retry": card_index, "increment_understood": True})
        else:
            notion_service.update_user_progress(user_id, {"current_index": card_index, "increment_understood": True})
        self.send_next_card(reply_token, user_id)

    def handle_card_not_sure(self, reply_token: str, user_id: str, card_index: int, is_retry: bool = False):
        """
        使用者點「😅 還不熟」：加入 retry_indices，累計待複習次數，立即跳下一張新卡。
        - 新卡（is_retry=False）：同步更新 current_index，避免 send_next_card 又取到同一張
        - 複習卡（is_retry=True）：不動 current_index，卡片留在 retry 佇列等下次
        """
        updates = {"add_retry": card_index, "increment_not_sure": True}
        if not is_retry:
            updates["current_index"] = card_index
        notion_service.update_user_progress(user_id, updates)
        self.send_next_card(reply_token, user_id, skip_retry=True)

    def handle_restart_review(self, reply_token: str, user_id: str):
        """
        使用者點「🔄 重新從頭複習」：重設 current_index 為 0、清空 retry_indices，再發第一張卡。
        """
        notion_service.update_user_progress(user_id, {"current_index": 0, "clear_retry": True})
        self.send_next_card(reply_token, user_id)

    def handle_next_card_click(self, reply_token: str, user_id: str, finished_index: int):
        """向下相容舊版「喵～我懂了」Postback，行為等同 handle_card_understood。"""
        self.handle_card_understood(reply_token, user_id, finished_index)

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

    def _derive_exam_type(self, exam_name: str) -> str:
        """從 exam_name 推導 Notion Exam_Type Select 值。"""
        if "中級" in exam_name:
            return "iPAS AI應用規劃師(中級)"
        return "iPAS AI應用規劃師(初級)"

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
