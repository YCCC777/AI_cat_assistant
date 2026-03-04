---
title: 貓咪助手 (AI 考照小幫手)
emoji: 🐈
colorFrom: yellow
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# 📚 AI 課程排課貓咪助手

這是一個為 AI 學習社群打造的 LINE Bot。它能自動解析訊息中的課程，並同步到 Google 行事曆與 Notion。

## ✨ 核心功能
- **可愛語氣**: 溫暖的「喵～」回應。
- **AI 解析**: 使用 Gemini 2.5 Flash-Lite 精準抓取。
- **雙向同步**: Google Calendar + Notion。
- **重複過濾**: MD5 訊息指紋，防刷屏。
- **成本控管**: 每日 Token 上限與個人限額。

## 🛠️ 技術棧
- **Language**: Python 3.12 (uv)
- **Framework**: FastAPI
- **Cloud**: Hugging Face Spaces (Docker)
- **AI**: Gemini 2.5 Flash-Lite

---

## 🔒 環境變數 (Secrets) 清單
在部署時，請在 Hugging Face 的 `Settings > Secrets` 頁面設定以下變數：

| 變數名稱 | 說明 |
| :--- | :--- |
| `LINE_CHANNEL_SECRET` | LINE Bot 的 Secret |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Bot 的 Access Token |
| `GEMINI_API_KEY` | Google Gemini API Key |
| `GOOGLE_CALENDAR_ID` | 您的 Google 日曆 ID |
| `NOTION_TOKEN` | Notion API 密鑰 |
| `NOTION_DATABASE_ID` | Notion 資料庫 ID |
| `ADMIN_LINE_USER_ID` | 管理員 (您) 的 LINE ID |
| `ADMIN_TRANSFER_PASSWORD` | 管理員特權密碼 (預設即可) |
| `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` | **(重點)** 將您的 `service_account.json` 內容全文貼入此欄位 |

---

## 🐱 為什麼我的貓咪沒反應？
1. 請檢查 `X-Line-Signature` 是否正確。
2. 請檢查 Webhook URL 是否包含 `/webhook` 結尾。
3. 檢查 Hugging Face 的日誌 (Logs) 是否有報錯。

*本專案開源且由 Gemini CLI 協助開發。*
