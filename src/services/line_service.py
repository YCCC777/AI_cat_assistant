from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    PushMessageRequest,
    TemplateMessage,
    ButtonsTemplate,
    PostbackAction,
    CarouselTemplate,
    CarouselColumn,
    MessageAction,
    QuickReply,
    QuickReplyItem,
    RichMenuRequest,
    RichMenuArea,
    RichMenuSize,
    RichMenuBounds,
)
from src.utils.config import settings
import logging
import os

logger = logging.getLogger(__name__)

class LineService:
    """
    負責 LINE 平台通訊的服務。
    """
    def __init__(self):
        self.configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
        self.api_client = ApiClient(self.configuration)
        self.messaging_api = MessagingApi(self.api_client)
        self.messaging_blob_api = MessagingApiBlob(self.api_client)

    def init_rich_menu(self, image_path: str = "image/rich_menu.jpg"):
        """
        初始化 Rich Menu (建立並設定為預設)。
        """
        try:
            # 1. 定義 Rich Menu 結構 (2500x1686 或 2500x843)
            # 這裡假設是一個 2500x843 的選單，分三個區域
            rich_menu_request = RichMenuRequest(
                size=RichMenuSize(width=2500, height=843),
                selected=True,
                name="貓咪助手功能選單",
                chat_bar_text="點我打開選單喵！🐾",
                areas=[
                    RichMenuArea(
                        bounds=RichMenuBounds(x=0, y=0, width=833, height=843),
                        action=MessageAction(label="AI 課程查詢", text="AI 課程查詢")
                    ),
                    RichMenuArea(
                        bounds=RichMenuBounds(x=833, y=0, width=834, height=843),
                        action=MessageAction(label="AI 資訊", text="AI 考試資訊")
                    ),
                    RichMenuArea(
                        bounds=RichMenuBounds(x=1667, y=0, width=833, height=843),
                        action=MessageAction(label="貓咪陪讀", text="貓咪陪讀")
                    )
                ]
            )

            # 2. 建立 Rich Menu
            rich_menu_id = self.messaging_api.create_rich_menu(rich_menu_request).rich_menu_id
            logger.info(f"Rich Menu 建立成功，ID: {rich_menu_id}")

            # 3. 上傳圖片 (如果檔案存在，使用 MessagingApiBlob 處理二進位)
            if os.path.exists(image_path):
                content_type = "image/jpeg" if image_path.endswith(".jpg") else "image/png"
                with open(image_path, "rb") as f:
                    self.messaging_blob_api.set_rich_menu_image(
                        rich_menu_id=rich_menu_id,
                        body=f.read(),
                        _headers={"Content-Type": content_type}
                    )
                logger.info("Rich Menu 圖片上傳成功。")
            else:
                logger.warning(f"找不到 Rich Menu 圖片 ({image_path})，將不進行圖片上傳。")

            # 4. 設定為全域預設
            self.messaging_api.set_default_rich_menu(rich_menu_id)
            logger.info("Rich Menu 已設定為全域預設。")
            
            return rich_menu_id
        except Exception as e:
            logger.error(f"初始化 Rich Menu 失敗: {str(e)}")
            return None

    def reply_text(self, reply_token: str, text: str):
        """
        發送文字回覆給使用者。
        """
        # 統一處理貓咪語氣 (如果回覆內容沒有喵)
        if "喵" not in text:
            text = f"{text} 喵～🐾"

        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text)]
                )
            )
        except Exception as e:
            logger.error(f"reply_text 失敗 (token={reply_token[:8]}...): {str(e)}")

    def reply_study_carousel(self, reply_token: str):
        """
        發送陪讀模組的輪播選單。
        """
        # 圖片連結模板：https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_xxxx.png
        carousel_template = CarouselTemplate(
            columns=[
                CarouselColumn(
                    thumbnail_image_url="https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_countdown.png?v=3",
                    title="捏肉球",
                    text="領取學習卡，開始今天的知識補給喵！",
                    actions=[
                        MessageAction(label="捏肉球領學習卡", text="捏肉球")
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url="https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_progress.png?v=3",
                    title="讀書進度",
                    text="查看目前讀書進度，看看累積了多少喵！",
                    actions=[
                        MessageAction(label="查看進度", text="讀書進度")
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url="https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_setting.png?v=3",
                    title="陪讀設定",
                    text="更改考試種類或設定考試日期喵！",
                    actions=[
                        MessageAction(label="陪讀設定", text="陪讀設定")
                    ]
                )
            ]
        )
        
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TemplateMessage(alt_text="貓咪陪讀選單喵！", template=carousel_template)]
                )
            )
        except Exception as e:
            logger.error(f"reply_study_carousel 失敗: {str(e)}")

    def reply_with_quick_reply(self, reply_token: str, text: str, options: list[tuple[str, str]]):
        """
        回傳帶有 Quick Reply 按鈕的訊息。
        options: [(label, text_to_send), ...]
        """
        quick_reply_items = [
            QuickReplyItem(action=MessageAction(label=label, text=msg))
            for label, msg in options
        ]
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text, quick_reply=QuickReply(items=quick_reply_items))]
                )
            )
        except Exception as e:
            logger.error(f"reply_with_quick_reply 失敗: {str(e)}")

    def reply_with_quick_reply_postback(self, reply_token: str, text: str, options: list[tuple[str, str, str]]):
        """
        回傳帶有 Postback Quick Reply 按鈕的訊息。
        options: [(label, postback_data, display_text), ...]
        label 最多 20 字，display_text 為點擊後顯示在聊天室的文字。
        """
        quick_reply_items = [
            QuickReplyItem(action=PostbackAction(label=label, data=data, display_text=display))
            for label, data, display in options
        ]
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text, quick_reply=QuickReply(items=quick_reply_items))]
                )
            )
        except Exception as e:
            logger.error(f"reply_with_quick_reply_postback 失敗: {str(e)}")

    def reply_messages(self, reply_token: str, texts: list):
        """
        一次回傳多則文字訊息（最多 5 則）。
        """
        messages = [TextMessage(text=t) for t in texts[:5]]
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=messages)
            )
        except Exception as e:
            logger.error(f"reply_messages 失敗: {str(e)}")

    def reply_check_in(
        self,
        reply_token: str,
        streak: int,
        exam_name: str | None,
        countdown: int | None,
        today_checkin_count: int = 0,
        next_milestone_hint: str | None = None,
        streak_milestone_msg: str | None = None,
    ):
        """
        每日第一次捏肉球的打卡訊息，附「翻開今日學習卡」Quick Reply 按鈕。
        """
        if streak == 1:
            streak_line = "🐾 第 1 天打卡！\n  本喵幫你記下來了喵！"
        else:
            streak_line = f"🐾 連續第 {streak} 天打卡！\n  本喵都快被主人感動哭了喵！"

        if exam_name and countdown is not None:
            if countdown > 0:
                exam_line = f"  ⏰ 考試倒數 {countdown} 天\n 目標考取： {exam_name}"
            elif countdown == 0:
                exam_line = f"  ⏰ 今天就是考試日！全力以赴喵！🔥\n 目標考取： {exam_name}"
            else:
                exam_line = f"  ⏰ 考試已過，辛苦了喵！🐾\n 目標考取： {exam_name}"
        else:
            exam_line = "  📝 還沒設定考試目標\n  點「陪讀設定」來設定吧！"

        lines = [streak_line]
        if streak_milestone_msg:
            lines.append(f"\n  {streak_milestone_msg}")
        lines.append(f"\n{exam_line}")
        if today_checkin_count > 1:
            lines.append(f"\n  👥 今天有 {today_checkin_count} 位夥伴一起努力")
        if next_milestone_hint:
            lines.append(f"\n  ✨ {next_milestone_hint}")

        text = "\n".join(lines)
        qr = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="📖 翻開今日學習卡", text="捏肉球"))
        ])
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text, quick_reply=qr)])
            )
        except Exception as e:
            logger.error(f"reply_check_in 失敗: {str(e)}")

    def reply_card_question(self, reply_token: str, chapter: str, card_index: int, question: str = "", is_retry: bool = False):
        """
        翻牌第一則：出題，顯示章節名稱與題目，附「看解答」Postback Quick Reply。
        複習卡標示 🔁，postback 帶 is_retry=1 供後續識別。
        """
        prefix = "🔁 複習卡" if is_retry else "📖 學習卡"
        lines = [f"{prefix} #{card_index}", f"💡【{chapter}】"]
        if question:
            lines.append(f"\n❓ {question}")
        else:
            lines.append("\n❓ 先回憶一下這個概念，準備好了嗎？")
        text = "\n".join(lines)
        retry_flag = "&is_retry=1" if is_retry else ""
        qr = QuickReply(items=[
            QuickReplyItem(action=PostbackAction(
                label="👀 看解答",
                data=f"action=reveal_card&index={card_index}{retry_flag}",
                display_text="看解答"
            ))
        ])
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text, quick_reply=qr)])
            )
        except Exception as e:
            logger.error(f"reply_card_question 失敗: {str(e)}")

    def reply_card_answer(self, reply_token: str, chapter: str, content: str, card_index: int, is_retry: bool = False):
        """
        翻牌第二則：揭曉完整解說，附「懂了」/「還不熟」/「回報」三個按鈕。
        is_retry 旗標透過 postback data 傳遞，讓 handle_card_understood 知道是否為複習卡。
        """
        answer_text = f"【{chapter}】\n\n{content}"
        retry_flag = "&is_retry=1" if is_retry else ""
        qr = QuickReply(items=[
            QuickReplyItem(action=PostbackAction(
                label="✅ 懂了！",
                data=f"action=card_understood&index={card_index}{retry_flag}",
                display_text="✅ 我懂了，換下一張！"
            )),
            QuickReplyItem(action=PostbackAction(
                label="😅 還不熟",
                data=f"action=card_not_sure&index={card_index}{retry_flag}",
                display_text="😅 還不熟，再複習一次"
            )),
            QuickReplyItem(action=PostbackAction(
                label="⚠️ 回報問題",
                data=f"action=report_card&index={card_index}",
                display_text="我想回報這張學習卡的問題"
            )),
        ])
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=answer_text, quick_reply=qr)])
            )
        except Exception as e:
            logger.error(f"reply_card_answer 失敗: {str(e)}")


    def reply_all_cards_done(self, reply_token: str):
        """
        所有學習卡都讀完時，顯示完成訊息 + Quick Reply「重新從頭複習」按鈕。
        """
        text = (
            "喵！🎉 恭喜主人把所有學習卡都捏完了！\n\n"
            "想再鞏固一次記憶嗎？\n"
            "點下方按鈕可以重新從頭複習喵！🐾"
        )
        qr = QuickReply(items=[
            QuickReplyItem(action=PostbackAction(
                label="🔄 重新從頭複習",
                data="action=restart_review",
                display_text="🔄 我要重新從頭複習！"
            )),
        ])
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text, quick_reply=qr)])
            )
        except Exception as e:
            logger.error(f"reply_all_cards_done 失敗: {str(e)}")

    def reply_learning_card(self, reply_token: str, chapter: str, content: str, next_index: int, countdown_days: int | None = None):
        """
        發送帶有「喵～我懂了」按鈕的學習卡。
        """
        card_text = f"📖【{chapter}】\n\n{content}"

        buttons_template = ButtonsTemplate(
            title="捏肉球時間 (學習卡)",
            text="讀完了嗎？點下方按鈕繼續喵～🐾",
            actions=[
                PostbackAction(
                    label="喵～我懂了 (換下一張)",
                    data=f"action=next_card&index={next_index}",
                    display_text="喵～我懂了！再捏一球！"
                ),
                PostbackAction(
                    label="⚠️ 回報卡片問題",
                    data=f"action=report_card&index={next_index}",
                    display_text="我想回報這張學習卡的問題"
                )
            ]
        )

        messages = []
        if countdown_days is not None:
            if countdown_days > 0:
                countdown_text = f"⏰ 距離考試還有 {countdown_days} 天，加油喵！🐾"
            elif countdown_days == 0:
                countdown_text = "⏰ 今天就是考試日！全力以赴喵！🐾🔥"
            else:
                countdown_text = f"⏰ 考試已過 {-countdown_days} 天，辛苦了喵！🐾"
            messages.append(TextMessage(text=countdown_text))
        messages.append(TextMessage(text=card_text))
        messages.append(TemplateMessage(alt_text="捏肉球時間喵！", template=buttons_template))

        self.messaging_api.reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=messages)
        )

    def reply_quiz_subject_selection(self, reply_token: str, subjects: list[str], exam_type: str = ""):
        """
        選科 Quick Reply（postback）。
        初級：「初級總共有科目一、科目二，這次要刷哪一科？」
        中級：「你報考了科目一、科目三，這次要刷哪一科？」
        """
        subject_labels = "、".join(subjects)
        if "初級" in exam_type:
            text = f"喵～初級總共有【{subject_labels}】，這次要刷哪一科的題目？"
        else:
            text = f"喵～你報考了【{subject_labels}】，這次要刷哪一科的題目？"
        options = [
            (s, f"action=quiz_select_subject&subject={s}", f"刷 {s} 的題目")
            for s in subjects
        ]
        self.reply_with_quick_reply_postback(reply_token, text, options)

    def reply_quiz_question(self, reply_token: str, question: dict):
        """
        刷題出題訊息。
        格式：📝【Chapter】\n題目\nA) ...\nB) ...\nC) ...\nD) ...
        Quick Reply：[A] [B] [C] [D] [結束刷題]
        """
        qid = question["qid"]
        text = (
            f"📝【{question['chapter']}】\n\n"
            f"{question['question']}\n\n"
            f"A) {question['option_a']}\n"
            f"B) {question['option_b']}\n"
            f"C) {question['option_c']}\n"
            f"D) {question['option_d']}"
        )
        qr = QuickReply(items=[
            QuickReplyItem(action=PostbackAction(
                label="A", data=f"action=quiz_answer&qid={qid}&choice=A", display_text="選 A")),
            QuickReplyItem(action=PostbackAction(
                label="B", data=f"action=quiz_answer&qid={qid}&choice=B", display_text="選 B")),
            QuickReplyItem(action=PostbackAction(
                label="C", data=f"action=quiz_answer&qid={qid}&choice=C", display_text="選 C")),
            QuickReplyItem(action=PostbackAction(
                label="D", data=f"action=quiz_answer&qid={qid}&choice=D", display_text="選 D")),
            QuickReplyItem(action=MessageAction(label="🚪 結束刷題", text="結束刷題")),
        ])
        try:
            self.messaging_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text, quick_reply=qr)])
            )
        except Exception as e:
            logger.error(f"reply_quiz_question 失敗: {e}")

    def reply_quiz_result(
        self, reply_token: str, is_correct: bool, chosen: str,
        question: dict, session: dict, is_final: bool = False
    ):
        """
        刷題結果訊息（對錯 + 解說 + 本場得分）。
        is_final=True 時顯示完整成績報告，不附「下一題」按鈕。
        """
        correct_letter = question["correct_answer"]
        correct_option = question.get(f"option_{correct_letter.lower()}", "")
        explanation = question.get("explanation", "（無解說）")

        if is_correct:
            header = "✅ 答對了！主人真厲害喵！🐾"
        else:
            header = f"😿 答錯了，別灰心喵！本喵幫你記住這題！\n\n你選：{chosen}\n正確答案：{correct_letter}) {correct_option}"

        score_line = f"\n\n本場：{session['total']} 題，答對 {session['correct']} 題 🎯"

        if is_final:
            accuracy = session["correct"] / session["total"] * 100
            if accuracy >= 80:
                grade_msg = "🔥 太強了！主人已經準備好考試了喵！"
            elif accuracy >= 60:
                grade_msg = "📚 還不錯！繼續加油，本喵看好你！"
            else:
                grade_msg = "🐾 多刷幾次，本喵陪你一起進步！"
            text = (
                f"{header}\n\n"
                f"💡 解說：\n{explanation}"
                f"{score_line}\n\n"
                f"━━━━━━━━━━━━━━\n"
                f"🎉 本場 {session['total']} 題刷完！\n"
                f"📊 正確率：{accuracy:.0f}%\n"
                f"{grade_msg}\n\n"
                f"錯題本喵幫你記下來，傳「餵罐罐」隨時繼續喵！🐾"
            )
            # 最終結果不附下一題按鈕
            try:
                self.messaging_api.reply_message(
                    ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
                )
            except Exception as e:
                logger.error(f"reply_quiz_result (final) 失敗: {e}")
        else:
            qid = question.get("qid", "")
            text = f"{header}\n\n💡 解說：\n{explanation}{score_line}"
            qr = QuickReply(items=[
                QuickReplyItem(action=PostbackAction(
                    label="➡️ 下一題", data="action=quiz_next", display_text="下一題！")),
                QuickReplyItem(action=PostbackAction(
                    label="⚠️ 回報問題", data=f"action=report_quiz&qid={qid}",
                    display_text="我想回報這道題的問題")),
                QuickReplyItem(action=MessageAction(label="🚪 結束刷題", text="結束刷題")),
            ])
            try:
                self.messaging_api.reply_message(
                    ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text, quick_reply=qr)])
                )
            except Exception as e:
                logger.error(f"reply_quiz_result 失敗: {e}")

    def push_text(self, to_user_id: str, text: str):
        """
        主動推播文字訊息給指定使用者（通常用於管理員通知）。
        """
        # 統一處理貓咪語氣
        if "喵" not in text:
            text = f"{text} 喵～🐾"
            
        self.messaging_api.push_message(
            PushMessageRequest(
                to=to_user_id,
                messages=[TextMessage(text=text)]
            )
        )

# 單例模式實例
line_service = LineService()
