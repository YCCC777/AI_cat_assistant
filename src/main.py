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
from src.utils.input_validator import validate_message, sanitize_url
from datetime import datetime
import logging
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)

# 等待使用者輸入回報內容的狀態 { user_id: card_index }
pending_reports: dict[str, int] = {}


@app.get("/")
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
        params = dict(param.split('=', 1) for param in data.split('&'))
        action = params.get("action")

        if action == "next_card":
            # 向下相容舊版按鈕
            finished_index = int(params.get("index", 0))
            study_service.handle_card_understood(reply_token, user_id, finished_index)

        elif action == "reveal_card":
            card_index = int(params.get("index", 0))
            study_service.handle_reveal_card(reply_token, card_index)

        elif action == "card_understood":
            card_index = int(params.get("index", 0))
            study_service.handle_card_understood(reply_token, user_id, card_index)

        elif action == "card_not_sure":
            study_service.handle_card_not_sure(reply_token)

        elif action == "report_card":
            card_index = int(params.get("index", 0))
            pending_reports[user_id] = card_index
            line_service.reply_text(
                reply_token,
                f"喵？主人覺得第 {card_index} 張學習卡哪裡有問題呢？\n請直接輸入您的意見（例如：答案有誤、內容看不懂），本喵會轉達給創作者！🐾"
            )

        elif action == "show_exam_dates":
            exam_name = params.get("exam", "")
            date_options = study_service.get_exam_date_options(exam_name)
            if date_options:
                line_service.reply_with_quick_reply_postback(
                    reply_token,
                    f"喵～請選擇您要報名的【{exam_name}】場次：",
                    date_options
                )
            else:
                line_service.reply_text(reply_token, "喵嗚...找不到考試日期資訊，請稍後再試或聯絡管理員喵～🐾")

        elif action == "register_exam":
            exam_name = params.get("exam", "")
            exam_date = params.get("date", "")
            reply = study_service.register_exam_direct(user_id, exam_name, exam_date)
            line_service.reply_text(reply_token, reply)

    except Exception as e:
        logger.error(f"Postback error: {str(e)}")


async def handle_text_message(event: MessageEvent):
    reply_token = event.reply_token
    message_text = event.message.text
    user_id = event.source.user_id

    logger.info(f"收到訊息 user={user_id[:8]}... text={message_text[:30]!r}")

    # 0. 防連打
    if user_limiter.is_too_fast(user_id):
        line_service.reply_text(reply_token, "喵～主人的手速太快了，本喵快跟不上了！請休息 3 秒鐘再傳訊息給我喵～🐾")
        return

    # 1. 回報狀態攔截（優先於所有指令）
    if user_id in pending_reports:
        card_index = pending_reports.pop(user_id)
        success = notion_service.create_card_report(card_index, user_id, message_text)
        if success:
            line_service.reply_text(reply_token, "已向本喵的創作者回報這張學習卡，感謝主人協助讓本喵變得更好！🐾")
            line_service.push_text(settings.ADMIN_LINE_USER_ID, f"⚠️ 學習卡回報\n卡片編號：#{card_index}\n回報者：{user_id}\n內容：{message_text}")
        else:
            line_service.reply_text(reply_token, "喵嗚...回報時出了點問題，請稍後再試或聯絡管理員喵～🐾")
        return

    # 2. 陪讀模組指令
    if message_text in ["陪讀設定", "報名", "陪讀報名"]:
        # 兩層選單：第一層選考試種類
        progress = notion_service.get_user_progress(user_id)
        if progress and progress.get("exam_name"):
            prefix = (
                f"目前本喵幫你追蹤的目標是【{progress['exam_name']}】，"
                f"考試日期 {progress['exam_date']}，"
                f"還有 {study_service._calculate_countdown(progress['exam_date'])} 天喵！\n\n"
                f"想換個新目標嗎？請選擇考試種類："
            )
        else:
            prefix = "喵～讓本喵幫你追蹤倒數和讀書進度吧！請選擇考試種類："
        exam_options = study_service.get_exam_type_options()
        line_service.reply_with_quick_reply_postback(reply_token, prefix, exam_options)
        return

    if message_text.startswith("報名"):
        # 保留文字格式相容，但嚴格驗證
        reply = study_service.register_exam(user_id, message_text)
        line_service.reply_text(reply_token, reply)
        return

    if message_text in ["捏肉球", "讀書", "學習卡"]:
        study_service.send_next_card(reply_token, user_id)
        return

    if message_text in ["倒數", "考試"]:
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
    if message_text == "AI 資訊":
        await handle_ai_exam_info(reply_token)
        return

    if message_text == "AI 課程":
        await handle_ai_courses(reply_token)
        return

    if message_text == "AI 考試資訊":
        await handle_ai_exam_info(reply_token)
        return

    if message_text == "AI 課程查詢":
        events = calendar_service.get_upcoming_events(days=7)
        if not events:
            reply = "喵～本喵翻遍整本行事曆了，接下來 7 天暫時沒有排課耶！趁現在好好充電，等好課出現本喵第一個通知主人喵～😸\n\n💡 小提醒：把課程訊息貼給本喵，我會自動幫您存進行事曆喔！"
        else:
            lines = [f"喵～找到了！接下來 7 天共有 {len(events)} 堂課等著主人喔！🐾\n"]
            for e in events:
                name = e.get("summary", "未知課程").replace("📚 ", "")
                start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
                link = e.get("location", "")
                # 格式化時間：2026-03-15T14:00:00+08:00 → 3/15 14:00
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(start)
                    time_str = f"{dt.month}/{dt.day} {dt.strftime('%H:%M')}"
                except Exception:
                    time_str = start[:16].replace("T", " ")
                entry = f"📚 {name}\n⏰ {time_str}"
                if link and link != "線上":
                    entry += f"\n🔗 {link}"
                lines.append(entry)
            reply = "\n---\n".join(lines)
        line_service.reply_text(reply_token, reply)
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

    # 4. 安全性驗證（短網址 / Prompt Injection）
    is_valid, reject_reason = validate_message(message_text)
    if not is_valid:
        if reject_reason == "short_url":
            line_service.reply_text(reply_token, "喵！這則訊息含有短網址，本喵不知道它會跑去哪裡，為了主人的安全先不記囉～🐾")
        else:
            line_service.reply_text(reply_token, "喵？這則訊息本喵看不太懂，沒辦法幫忙記下來喵～🐾")
        logger.warning(f"訊息被安全過濾 reason={reject_reason} user={user_id[:8]}")
        return

    # 5. 重複訊息過濾
    if deduplicator.is_duplicate(message_text):
        line_service.reply_text(reply_token, "喵？這則訊息本喵好像已經記過囉！重複的就不再記一次了喵～🐾")
        return

    # 6. Token 額度檢查
    if token_limiter.is_limit_exceeded():
        line_service.reply_text(reply_token, "喵～不好意思，本喵今天的額度用完了，要先去睡覺了捏！明天再來吧喵～😴")
        return

    # 7. 使用者個人限額
    if user_limiter.is_limit_exceeded(user_id):
        line_service.reply_text(reply_token, f"喵～主人的群友太熱情了！但您今天已經記了 {settings.USER_DAILY_LIMIT} 場課程，本喵的手手快抽筋了喵！明天再幫您記唷！🐾")
        return

    # 8. AI 解析與寫入
    await process_and_reply(reply_token, message_text, user_id)


async def handle_ai_courses(reply_token: str):
    events = calendar_service.get_upcoming_events(days=7)
    if not events:
        line_service.reply_text(reply_token, "喵～本喵翻遍行事曆了，未來 7 天暫時沒有排課耶！等好課出現本喵第一個通知喵～😸")
        return
    lines = [f"📅 未來 7 天共 {len(events)} 堂課："]
    for e in events:
        name = e.get("summary", "未知課程").replace("📚 ", "")
        start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
        try:
            dt = datetime.fromisoformat(start)
            time_str = f"{dt.month}/{dt.day} {dt.strftime('%H:%M')}"
        except Exception:
            time_str = start[:16].replace("T", " ")
        lines.append(f"• {name}（{time_str}）")
    line_service.reply_text(reply_token, "\n".join(lines))


async def handle_ai_exam_info(reply_token: str):
    from src.utils.info_cache import get_cached_info, fetch_and_cache_ipas_news
    try:
        data = get_cached_info() or fetch_and_cache_ipas_news()
        fetched_dt = datetime.fromisoformat(data["fetched_at"])
        date_str = f"{fetched_dt.year}年{fetched_dt.month:02d}月{fetched_dt.day:02d}日"
        lines = [f"喵～以下是本喵 {date_str} 趁大家不注意、悄悄出任務爬回來的 iPAS 最新消息！主人請慢用 🐾\n"]
        for item in data["news"][:3]:
            lines.append(f"📌 {item['title']}\n🔗 {item['url']}\n({item['date']})")
        line_service.reply_text(reply_token, "\n\n".join(lines))
    except Exception as e:
        logger.error(f"handle_ai_exam_info 失敗: {e}")
        line_service.reply_text(reply_token, "喵嗚...本喵出任務失敗了，iPAS 官網好像在睡覺，請稍後再試喵～🐾")


async def process_and_reply(reply_token: str, message_text: str, user_id: str):
    try:
        result = await gemini_service.parse_course_info(message_text)
        token_limiter.add_usage(200)

        courses = result if isinstance(result, list) else [result]

        reply_msgs = []
        for course_info in courses:
            if not course_info.is_course:
                logger.info(f"AI 判定非課程: {course_info.reason}")
                reply_msgs.append("喵？這看起來不像 AI 課程資訊耶...是不是被本喵的魅力給迷倒輸入錯誤呢？")
                continue

            # L3: 寫入前 sanitize URL（短網址或非 allowlist 一律清除）
            course_info.location_url = sanitize_url(course_info.location_url)

            calendar_service.add_event(course_info)
            notion_service.add_course(course_info)

            url_display = course_info.location_url or "（連結不符安全規則，已移除）"
            reply_msgs.append(
                f"📚 {course_info.name}\n"
                f"⏰ {course_info.date_time}\n"
                f"🔗 {url_display}"
            )

        final_msg = "喵～記下來囉！🐾\n\n" + "\n---\n".join(reply_msgs)
        line_service.reply_text(reply_token, final_msg)
        user_limiter.add_usage(user_id)

    except Exception as e:
        logger.error(f"process_and_reply 出錯: {type(e).__name__}: {str(e)}", exc_info=True)
        line_service.reply_text(reply_token, "喵嗚...本喵腦袋打結了，請稍後再試一次！🐾")


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.PORT, reload=(settings.ENV == "development"))
