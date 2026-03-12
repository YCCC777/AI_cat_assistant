import random
import logging
from src.services.notion_service import notion_service
from src.services.line_service import line_service

logger = logging.getLogger(__name__)

QUIZ_SESSION_LIMIT = 50  # 每輪題數


class QuizService:
    """
    刷題系統業務邏輯（餵罐罐）。
    與學習卡系統（捏肉球）完全獨立。

    Session 結構（in-memory）：
    quiz_sessions[user_id] = {
        "correct":  int,            # 本輪答對數
        "total":    int,            # 本輪已答題數
        "pool":     [qid, ...],     # 本輪剩餘題目佇列（已洗牌）
        "subjects": list | None,    # 初級=None；中級=["科目一","科目三"]
        "exam_type": str,
    }

    每輪開始時組建 pool：
      - 上一輪的錯題（Wrong_Queue）全部必含
      - 剩餘名額從未答過的題目中隨機補齊
      - 全部洗牌後依序出題

    中級上線時只需：
      1. 在報名流程加入「選科」步驟，寫入 Quiz_Progress_DB.Selected_Subjects
      2. _get_exam_info 讀出 selected_subjects 並傳入 _build_session_pool
      程式其他部分不需改動。
    """

    def handle_feed_can(self, reply_token: str, user_id: str, quiz_sessions: dict):
        """
        「餵罐罐」入口。
        - 初級 / 中級單科 → 直接建立 session pool，送出第一題
        - 中級多科 → 先顯示選科 Quick Reply，等用戶點選後再走 handle_subject_selected
        """
        progress = notion_service.get_user_progress(user_id)
        if not progress or not progress.get("exam_name") or progress["exam_name"] == "未設定":
            line_service.reply_text(
                reply_token,
                "喵？要先設定考試目標才能刷題喔！\n請點選「陪讀設定」來設定，本喵幫你準備練習題！🐾"
            )
            return

        exam_type, subjects = self._get_exam_info(user_id, progress["exam_name"])

        if not subjects:
            line_service.reply_text(reply_token, "喵嗚...找不到你的報考科目，請先完成陪讀設定喵！🐾")
            return

        # 多科目 → 先選科再開始（初級必定兩科，中級依報考科目）
        if len(subjects) > 1:
            line_service.reply_quiz_subject_selection(reply_token, subjects, exam_type=exam_type)
            return

        self._start_quiz(reply_token, user_id, exam_type, subjects, quiz_sessions)

    def handle_subject_selected(
        self, reply_token: str, user_id: str, subject: str, quiz_sessions: dict
    ):
        """
        中級用戶選完科目後的入口（postback: action=quiz_select_subject&subject=科目一）。
        初級選科後也走這裡。
        """
        progress = notion_service.get_user_progress(user_id)
        exam_name = progress.get("exam_name", "") if progress else ""
        if "中級" in exam_name:
            exam_type = "iPAS AI應用規劃師(中級)"
        else:
            exam_type = "iPAS AI應用規劃師(初級)"
        self._start_quiz(reply_token, user_id, exam_type, [subject], quiz_sessions)

    def handle_quiz_answer(
        self, reply_token: str, user_id: str, qid: str, choice: str, quiz_sessions: dict
    ):
        """用戶選擇 A/B/C/D 後的處理。"""
        question = notion_service.get_quiz_question(qid)
        if not question:
            line_service.reply_text(reply_token, "喵嗚...找不到這道題，請重新傳「餵罐罐」開始刷題喵～")
            return

        correct_answer = question.get("correct_answer", "")
        if not correct_answer:
            logger.error(f"題目 {qid} 的 correct_answer 是空的！請檢查 Notion 資料。")
            line_service.reply_text(
                reply_token,
                f"喵嗚...題目 {qid} 的正確答案資料有問題，本喵已通報管理員喵！\n請傳「餵罐罐」繼續刷其他題！🐾"
            )
            return

        is_correct = (choice.upper() == correct_answer.upper())

        session = quiz_sessions.setdefault(user_id, {"correct": 0, "total": 0, "pool": [], "subjects": None, "exam_type": ""})
        session["total"] += 1
        if is_correct:
            session["correct"] += 1

        exam_type = session.get("exam_type", "")
        updates: dict = {"increment_total": True, "add_answered": qid}
        if is_correct:
            updates["increment_correct"] = True
            updates["remove_wrong_queue"] = qid
        else:
            updates["add_wrong_queue"] = qid
        notion_service.update_quiz_progress(user_id, updates, exam_type=exam_type)

        if session["total"] >= QUIZ_SESSION_LIMIT:
            line_service.reply_quiz_result(
                reply_token, is_correct, choice.upper(), question, session, is_final=True
            )
            quiz_sessions.pop(user_id, None)
        else:
            line_service.reply_quiz_result(
                reply_token, is_correct, choice.upper(), question, session, is_final=False
            )

    def handle_quiz_next(self, reply_token: str, user_id: str, quiz_sessions: dict):
        """「下一題」Postback：從 pool 取下一題。"""
        session = quiz_sessions.get(user_id)
        if not session:
            line_service.reply_text(
                reply_token,
                "喵？本場刷題紀錄不見了（可能是伺服器重啟喵）\n請重新傳「餵罐罐」開始新的一輪！🐾"
            )
            return
        self._pop_and_send(reply_token, user_id, quiz_sessions)

    def handle_quiz_end(self, reply_token: str, user_id: str, quiz_sessions: dict):
        """用戶傳「結束刷題」：顯示本場成績後清除 session。"""
        session = quiz_sessions.pop(user_id, None)
        if session and session["total"] > 0:
            accuracy = session["correct"] / session["total"] * 100
            line_service.reply_text(
                reply_token,
                f"喵！本場刷題結束！\n\n"
                f"🎯 答題數：{session['total']} 題\n"
                f"✅ 答對：{session['correct']} 題\n"
                f"📊 正確率：{accuracy:.0f}%\n\n"
                f"錯題本喵幫你記下來了，下輪刷題時必定會再出現喵！🐾"
            )
        else:
            line_service.reply_text(reply_token, "喵！下次繼續加油！本喵等你回來刷題喵～🐾")

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    def _start_quiz(
        self, reply_token: str, user_id: str,
        exam_type: str, subjects: list[str] | None, quiz_sessions: dict
    ):
        """pool 組建 → session 寫入 → 送出第一題（初級與中級選科後的共用入口）。"""
        pool = self._build_session_pool(user_id, exam_type, subjects)
        if not pool:
            line_service.reply_text(
                reply_token,
                "喵嗚...題庫還在準備中，請稍後再試，或聯絡管理員！🐾"
            )
            return
        quiz_sessions[user_id] = {
            "correct":   0,
            "total":     0,
            "pool":      pool,
            "subjects":  subjects,
            "exam_type": exam_type,
        }
        self._pop_and_send(reply_token, user_id, quiz_sessions)

    def _get_exam_info(self, user_id: str, exam_name: str) -> tuple[str, list[str]]:
        """
        從 exam_name 推導 exam_type 與可選科目清單。

        初級：科目一、科目二 均為必考，固定回傳兩科供用戶選擇要刷哪科。
        中級：從 Quiz_Progress_DB.Selected_Subjects 讀取用戶報考的科目。
        """
        if "中級" in exam_name:
            exam_type = "iPAS AI應用規劃師(中級)"
            quiz_progress = notion_service.get_quiz_progress(user_id)
            subjects = (quiz_progress.get("selected_subjects") or []) if quiz_progress else []
        else:
            exam_type = "iPAS AI應用規劃師(初級)"
            subjects = ["科目一", "科目二"]  # 初級兩科均為必考，每次讓用戶選要刷哪科
        return exam_type, subjects

    def _build_session_pool(
        self, user_id: str, exam_type: str, subjects: list[str] | None = None
    ) -> list[str]:
        """
        組建本輪 50 題的題目 ID 池：
          1. 上一輪錯題（Wrong_Queue）→ 全部必含
          2. 剩餘名額從未答過的題中隨機補齊
          3. 新題不足時從已答過的題（排除錯題）中補
          4. 整體洗牌

        subjects: 初級傳 None；中級傳 ["科目一", "科目三"] 等。
        """
        quiz_progress = notion_service.get_quiz_progress(user_id, exam_type=exam_type)
        wrong_queue: list[str] = quiz_progress["wrong_queue"] if quiz_progress else []
        answered_ids: list[str] = quiz_progress["answered_ids"] if quiz_progress else []

        all_ids = notion_service.get_all_quiz_question_ids(exam_type, subjects=subjects)
        if not all_ids:
            return []

        wrong_set = set(wrong_queue)
        answered_set = set(answered_ids)

        must_include = [qid for qid in wrong_queue if qid in all_ids]
        fresh = [qid for qid in all_ids if qid not in wrong_set and qid not in answered_set]
        remaining = max(0, QUIZ_SESSION_LIMIT - len(must_include))

        if len(fresh) >= remaining:
            fill = random.sample(fresh, remaining)
        else:
            loopback = [qid for qid in all_ids if qid not in wrong_set and qid in answered_set]
            combined = fresh + loopback
            fill = random.sample(combined, min(remaining, len(combined)))

        pool = must_include + fill
        random.shuffle(pool)
        return pool

    def _pop_and_send(self, reply_token: str, user_id: str, quiz_sessions: dict):
        """從 session pool 取下一題並發送。"""
        session = quiz_sessions.get(user_id)
        if not session or not session.get("pool"):
            line_service.reply_text(
                reply_token,
                "喵！本輪所有題目都答完了！傳「餵罐罐」開始新的一輪喵～🐾"
            )
            quiz_sessions.pop(user_id, None)
            return

        qid = session["pool"].pop(0)
        question = notion_service.get_quiz_question(qid)
        if not question:
            logger.warning(f"題目 {qid} 在 Notion 找不到，跳過")
            self._pop_and_send(reply_token, user_id, quiz_sessions)
            return

        line_service.reply_quiz_question(reply_token, question)


quiz_service = QuizService()
