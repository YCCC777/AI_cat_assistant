from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
from src.services.line_service import line_service
from src.services.gemini_service import gemini_service
from src.services.calendar_service import calendar_service
from src.services.notion_service import notion_service
from src.services.study_service import study_service
from src.utils.config import settings
from src.utils.deduplicator import deduplicator
from src.utils.limiter import token_limiter
from src.utils.user_limiter import user_limiter
import logging
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        events = parser.parse(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook parse error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    for event in events:
        if isinstance(event, PostbackEvent):
            background_tasks.add_task(handle_postback, event)
        elif isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            background_tasks.add_task(handle_text_message, event)

    return {"status": "ok"}


async def handle_postback(event: PostbackEvent):
    user_id = event.source.user_id
    reply_token = event.reply_token
    data = event.postback.data

    if user_limiter.is_too_fast(user_id):
        line_service.reply_text(reply_token, "喵～大家太熱情了，本喵的肉球忙不過來，請等 3 秒鐘再點一次喔！🐾")
        return

    try:
        params = dict(param.split('=') for param in data.split('&'))
        if params.get("action") == "next_card":
            finished_index = int(params.get("index", 0))
            study_service.handle_next_card_click(reply_token, user_id, finished_index)
    except Exception as e:
        logger.error(f"Postback error: {str(e)}")


async def handle_text_message(event: MessageEvent):
    reply_token = event.reply_token
    message_text = event.message.text
    user_id = event.source.user_id

    # 0. 防連打
    if user_limiter.is_too_fast(user_id):
        line_service.reply_text(reply_token, "喵～主人的手速太快了，本喵快跟不上了！請休息 3 秒鐘再傳訊息給我喵～🐾")
        return

    # 1. 陪讀模組指令
    if message_text.startswith("報名"):
        reply = study_service.register_exam(user_id, message_text)
        line_service.reply_text(reply_token, reply)
        return

    if message_text in ["餵罐罐", "罐罐", "讀書", "學習卡"]:
        study_service.send_next_card(reply_token, user_id)
        return

    if message_text in ["捏肉球", "倒數", "考試"]:
        reply = study_service.get_countdown_msg(user_id)
        line_service.reply_text(reply_token, reply)
        return

    if message_text in ["讀書進度", "進度", "計畫"]:
        reply = study_service.get_study_menu(user_id)
        line_service.reply_text(reply_token, reply)
        return

    if "貓咪陪讀" in message_text:
        line_service.reply_study_carousel(reply_token)
        return

    # 2. 固定回覆指令
    if message_text == "AI 課程查詢":
        line_service.reply_text(reply_token, "喵～主人，您只要直接把想記下來的「課程訊息」或「網址」貼給本喵，我就會自動幫您塞進去行事曆跟 Notion 囉！🐾")
        return

    if message_text == "AI 週報":
        line_service.reply_text(reply_token, "喵嗚～週報模組還在貓咪產房努力中！預計 Phase 3 就會跟大家見面了，主人再等等本喵喔～🐾")
        return

    # 3. 管理員指令
    if message_text == "更新選單" and user_id == settings.ADMIN_LINE_USER_ID:
        rich_menu_id = line_service.init_rich_menu()
        if rich_menu_id:
            line_service.reply_text(reply_token, f"喵！選單更新成功囉！\nID: {rich_menu_id}")
        else:
            line_service.reply_text(reply_token, "喵嗚...選單更新失敗了，請檢查伺服器日誌。")
        return

    # 4. 重複訊息過濾
    if deduplicator.is_duplicate(message_text):
        line_service.reply_text(reply_token, "喵？這則訊息本喵好像已經記過囉！重複的就不再記一次了喵～🐾")
        return

    # 5. Token 額度檢查
    if token_limiter.is_limit_exceeded():
        line_service.reply_text(reply_token, "喵～不好意思，本喵今天的額度用完了，要先去睡覺了捏！明天再來吧喵～😴")
        return

    # 6. 使用者個人限額
    if user_limiter.is_limit_exceeded(user_id):
        line_service.reply_text(reply_token, f"喵～主人的群友太熱情了！但您今天已經記了 {settings.USER_DAILY_LIMIT} 場課程，本喵的手手快抽筋了喵！明天再幫您記唷！🐾")
        return

    # 7. AI 解析與寫入
    await process_and_reply(reply_token, message_text, user_id)


async def process_and_reply(reply_token: str, message_text: str, user_id: str):
    try:
        result = await gemini_service.parse_course_info(message_text)
        token_limiter.add_usage(200)

        courses = result if isinstance(result, list) else [result]

        reply_msgs = []
        for course_info in courses:
            if not course_info.is_course:
                reply_msgs.append(f"📚 {course_info.name or '未知課程'}: 喵？這看起來不像 AI 課程資訊耶...是不是被本喵的魅力給迷倒輸入錯誤呢？")
                continue

            calendar_service.add_event(course_info)
            notion_service.add_course(course_info)

            reply_msgs.append(
                f"📚 {course_info.name}\n"
                f"⏰ {course_info.date_time}\n"
                f"🔗 {course_info.location_url or '無連結'}"
            )

        final_msg = "喵～記下來囉！🐾\n\n" + "\n---\n".join(reply_msgs)
        line_service.reply_text(reply_token, final_msg)
        user_limiter.add_usage(user_id)

    except Exception as e:
        logger.error(f"處理訊息時出錯: {str(e)}")
        line_service.reply_text(reply_token, "喵？這看起來不像 AI 課程資訊耶...是不是被本喵的魅力給迷倒輸入錯誤呢？")


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.PORT, reload=(settings.ENV == "development"))
