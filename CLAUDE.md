# 社群專用排課小助手 — 專案筆記 (CLAUDE.md)

## 專案概覽

LINE Bot 貓咪助手，部署在 Hugging Face Spaces (Docker)。

| 項目 | 內容 |
|------|------|
| 語言 | Python 3.12 |
| Web框架 | FastAPI + uvicorn (port 7860) |
| 套件管理 | uv |
| LINE SDK | line-bot-sdk v3 (linebot.v3) |
| AI 模型 | Gemini 2.5 Flash Lite (`gemini-2.5-flash-lite`) — 確認為有效模型，使用 `google-genai` 新 SDK |
| 部署平台 | Hugging Face Spaces (`LisaCC/AI-Cat-Assistant`) |
| 圖片 Repo | GitHub `YCCC777/AI_cat_assistant` (origin) |

## Git 分支與部署策略

| 分支 | Remote | 用途 |
|------|--------|------|
| `main` | `origin` (GitHub) | 開發主線，含圖片檔案 |
| `hf-deploy` | `hf` (HF Spaces) | 部署分支，**無 binary 圖片**，HF 才能接受 |

**工作流程**：
1. 開發在 `main` → push 到 `origin`
2. 部署時：`git checkout hf-deploy` → `git merge main` → `git push hf hf-deploy:main --force`
3. 切回：`git checkout main`

> ⚠️ HF Token 更新後需執行：
> `git remote set-url hf https://LisaCC:<新TOKEN>@huggingface.co/spaces/LisaCC/AI-Cat-Assistant`

> 注意：HF Spaces 拒絕 binary commit，`hf-deploy` 分支永遠不 commit 圖片（Dockerfile 在 build 時用 curl 從 GitHub 下載）

## 已確認的 Bugs 與修復狀態

### Bug 1 — `asyncio.create_task()` 在同步 LINE handler 中 ✅ 已修復 (2026-03-05)
- **位置**：`src/main.py`
- **修復**：`WebhookHandler` → `WebhookParser` + FastAPI `BackgroundTasks`
  所有 handler callback 改為 `async def`，完全正確的非同步流程

### Bug 2 — 輪播圖片過大 + `.gitignore` 排除 ✅ 已修復 (2026-03-05)
- **問題 A**：`.gitignore` 有 `image/`，改為只排除影音大檔（GitHub branch）
- **問題 B（主因）**：圖片各約 7MB，LINE 輪播縮圖上限為 **1MB**
- **修復**：壓縮至 779–871KB，1024×686px

### Bug 3 — Gemini 模型名稱 ✅ 確認無誤
- `gemini-2.5-flash-lite` 是有效的穩定 API 模型（2025/07 GA）

### Bug 4 — Rich Menu 圖片上傳用錯 API Client ✅ 已修復 (2026-03-05)
- **位置**：`src/services/line_service.py`
- **問題 A**：`set_rich_menu_image` 需要 `MessagingApiBlob`，不是 `MessagingApi`
- **問題 B**：圖片檔名雙副檔名 `rich_menu.png.png`，改為 `rich_menu.jpg`
- **修復**：新增 `self.messaging_blob_api = MessagingApiBlob(self.api_client)`，圖片改 JPEG (257KB)

## 架構說明

```
src/
├── main.py              # FastAPI app + WebhookParser + BackgroundTasks 路由
├── models/
│   └── course.py        # CourseInfo / TokenUsage Pydantic model
├── services/
│   ├── line_service.py  # LINE Bot API 封裝 (reply, push, rich menu, carousel)
│   ├── gemini_service.py# Gemini AI 解析服務 (google-genai, native async)
│   ├── calendar_service.py # Google Calendar API
│   ├── notion_service.py   # Notion API (課程DB + 陪讀進度DB + 學習卡DB)
│   └── study_service.py    # 陪讀模組業務邏輯
└── utils/
    ├── config.py        # pydantic-settings 環境變數設定
    ├── deduplicator.py  # 重複訊息過濾
    ├── limiter.py       # 每日 Token 額度限制
    └── user_limiter.py  # 使用者個人限額 + 防連打
```

## 必要環境變數 (.env)

```env
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
GEMINI_API_KEY=
GEMINI_MODEL_NAME=gemini-2.5-flash-lite   # 可選，已有預設值
GOOGLE_CALENDAR_ID=
GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT=      # HF 部署用 (JSON 字串)
NOTION_TOKEN=
NOTION_DATABASE_ID=
NOTION_USER_PROGRESS_DB_ID=              # 可選 (陪讀功能)
NOTION_LEARNING_CARD_DB_ID=             # 可選 (陪讀功能)
ADMIN_LINE_USER_ID=
```

## 輪播圖片路徑規則

圖片存放在 `image/` 資料夾（僅 GitHub origin，不推 HF），透過 raw URL 供 LINE 顯示：
```
https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/{filename}.png
```

目前圖片：`card_learning.png`, `card_countdown.png`, `card_progress.png`, `card_setting.png`

Rich Menu 圖片：`image/rich_menu.jpg`（Dockerfile build 時自動從 GitHub 下載）

## 重要決策記錄

| 日期 | 決策 |
|------|------|
| 2026-03-05 | 放棄 Gemini CLI 生成的程式碼架構，改由 Claude Code 重構 |
| 2026-03-05 | 確認 `gemini-2.5-flash-lite` 為有效模型（不需更換） |
| 2026-03-05 | 遷移 Gemini SDK：`google-generativeai`（已停止維護）→ `google-genai`（新版，有原生 async） |
| 2026-03-05 | 輪播圖片存 GitHub，carousel 用 raw URL；Rich Menu 圖片由 Dockerfile build 時下載 |
| 2026-03-05 | HF Spaces 拒絕 binary commit，建立 `hf-deploy` orphan 分支（無圖片歷史）供 HF 部署 |
