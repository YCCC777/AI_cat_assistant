from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    PushMessageRequest,
    TemplateMessage,
    ButtonsTemplate,
    PostbackAction,
    CarouselTemplate,
    CarouselColumn,
    MessageAction,
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from src.utils.config import settings

class LineService:
    """
    負責 LINE 平台通訊的服務。
    """
    def __init__(self):
        # 初始化 LINE 配置
        self.configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
        self.handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
        self.api_client = ApiClient(self.configuration)
        self.messaging_api = MessagingApi(self.api_client)

    def reply_text(self, reply_token: str, text: str):
        """
        發送文字回覆給使用者。
        """
        # 統一處理貓咪語氣 (如果回覆內容沒有喵)
        if "喵" not in text:
            text = f"{text} 喵～🐾"
            
        self.messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )

    def reply_study_carousel(self, reply_token: str):
        """
        發送陪讀模組的輪播選單。
        """
        # 圖片連結模板：https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_xxxx.png
        carousel_template = CarouselTemplate(
            columns=[
                CarouselColumn(
                    thumbnail_image_url="https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_learning.png",
                    title="餵罐罐時間",
                    text="來領取下一張 AI 學習卡喵！",
                    actions=[
                        MessageAction(label="領取罐罐", text="餵罐罐")
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url="https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_countdown.png",
                    title="捏捏肉球",
                    text="查看考試倒數天數，給您打氣喵！",
                    actions=[
                        MessageAction(label="查看倒數", text="捏肉球")
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url="https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_progress.png",
                    title="讀書進度",
                    text="看看目前讀了多少罐罐喵！",
                    actions=[
                        MessageAction(label="查看進度", text="讀書進度")
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url="https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/card_setting.png",
                    title="陪讀設定",
                    text="想要修改考試日期或名稱嗎喵？",
                    actions=[
                        MessageAction(label="重新設定", text="報名")
                    ]
                )
            ]
        )
        
        self.messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TemplateMessage(alt_text="貓咪陪讀選單喵！", template=carousel_template)]
            )
        )

    def reply_learning_card(self, reply_token: str, chapter: str, content: str, next_index: int):
        """
        發送帶有「喵～我懂了」按鈕的學習卡。
        """
        text = f"【{chapter}】\n\n{content}\n\n加油喵！讀完點一下按鈕喔～🐾"
        
        # 確保文字不超過 160 字 (LINE 限制)
        display_text = text if len(text) <= 160 else text[:157] + "..."
        
        buttons_template = ButtonsTemplate(
            title="罐罐時間 (學習卡)",
            text=display_text,
            actions=[
                PostbackAction(
                    label="喵～我懂了 (換下一張)",
                    data=f"action=next_card&index={next_index}",
                    display_text="喵～我懂了！再來一份罐罐！"
                )
            ]
        )
        
        self.messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TemplateMessage(alt_text="餵罐罐時間喵！", template=buttons_template)]
            )
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

    async def handle_webhook(self, body: str, signature: str):
        """
        處理 Webhook 並將事件傳遞給 handler。
        """
        try:
            self.handler.handle(body, signature)
        except InvalidSignatureError:
            raise Exception("Invalid signature")

# 單例模式實例
line_service = LineService()
