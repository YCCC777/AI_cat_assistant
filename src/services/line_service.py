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
