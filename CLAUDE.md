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

### 日常更新部署流程

```bash
# Step 1：開發完推 GitHub
git checkout main
git add <改動的檔案>
git commit -m "..."
git push origin main

# Step 2：同步到 HF 部署分支
git checkout hf-deploy
git checkout main -- src/ Dockerfile pyproject.toml uv.lock CLAUDE.md
# ⚠️ 不要 git merge main（會帶入 image/ 的刪除記錄）
git add -A
git commit -m "deploy: sync from main YYYY-MM-DD"

# Step 3：推到 HF Spaces
git push hf hf-deploy:main --force

# Step 4：切回繼續開發
git checkout main
```

> ⚠️ HF Token 更新後需執行（token 絕對不要 commit 進 git！）：
> `git remote set-url hf https://LisaCC:<新TOKEN>@huggingface.co/spaces/LisaCC/AI-Cat-Assistant`

> 注意：HF Spaces 拒絕 binary commit，`hf-deploy` 分支永遠不 commit 圖片。
> 不要用 `git merge main`，改用 `git checkout main -- <files>` 逐一同步程式碼檔案。

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
│   ├── line_service.py  # LINE Bot API 封裝 (reply, push, rich menu, carousel, quick reply)
│   ├── gemini_service.py# Gemini AI 解析服務 (google-genai, native async)
│   ├── calendar_service.py # Google Calendar API
│   ├── notion_service.py   # Notion API (課程DB + 陪讀進度DB + 學習卡DB)
│   └── study_service.py    # 陪讀模組業務邏輯
└── utils/
    ├── config.py        # pydantic-settings 環境變數設定
    ├── deduplicator.py  # 重複訊息過濾
    ├── limiter.py       # 每日 Token 額度限制
    ├── user_limiter.py  # 使用者個人限額 + 防連打
    └── info_cache.py    # iPAS 爬蟲 + 7天快取（/tmp/ipas_news_cache.json）
```

## 指令對應表（使用者輸入 → 功能）

| 輸入 | 功能 |
|------|------|
| `AI 資訊` | Quick Reply 問使用者要看哪種資訊 |
| `AI 課程` | 顯示 Google Calendar 未來 7 天課程 |
| `AI 考試資訊` | 顯示 iPAS 最新消息（爬蟲，7天快取） |
| `捏肉球` / `餵罐罐` | 領取學習卡（附帶考試倒數提醒） |
| `讀書進度` | 顯示目前讀書進度 + 倒數天數 |
| `貓咪陪讀` | 顯示陪讀 carousel（3張卡） |
| `報名 [考試] [日期]` | 設定考試目標 |
| `AI 課程查詢` | 同「AI 課程」（舊指令，保留相容） |
| `更新選單`（管理員）| 重新初始化 Rich Menu |

## iPAS 爬蟲說明

- **檔案**：`src/utils/info_cache.py`
- **API**：`https://www.ipas.org.tw/api/proxy/certification/AIAP/news/list`
  - ⚠️ 此為網站內部非公開 API，未來改版可能失效，只需更新 `IPAS_API` 常數即可
  - 逆向方式：讀取 Next.js chunk `app/(default)/certification/[id]/news/page-*.js`
- **快取**：`/tmp/ipas_news_cache.json`，7天更新一次
- **連結格式**：`https://www.ipas.org.tw/certification/AIAP/news/{code}`

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
| 2026-03-06 | 捏肉球改為領取學習卡功能；倒數整合進讀書進度；carousel 從 4 張減為 3 張 |
| 2026-03-06 | AI 資訊改用 Quick Reply 互動問答，分為「AI 課程」與「iPAS 最新消息」兩條路徑 |
| 2026-03-06 | 考試資訊捨棄 Gemini Grounding，改用 iPAS 官方內部 API 爬蟲（零 token、7天快取） |
| 2026-03-08 | 陪讀設定改為兩層 Quick Reply Postback（選考試種類 → 選日期），嚴格驗證只接受 iPAS 初級 |
| 2026-03-08 | 新增 `exam_dates.py`：115年4場初級考試日期 hard-code，每年年份不符時自動爬蟲更新 |
| 2026-03-09 | 簡化學習卡流程：拿掉「看完整解說」中間步驟，看解答直接顯示完整 Content + 三個按鈕 |

## 已知待改項目

### 「😅 還不熟」後跳出的仍是同一張卡（待修復）
- **現況**：點「還不熟」後，`handle_card_not_sure()` 把該卡加入 `retry_indices` 再呼叫 `send_next_card()`，但 `send_next_card()` 看到 retry 佇列非空，又立刻重發剛加入的同一張卡
- **期望行為**：點「還不熟」後跳到下一張**新卡**，被標記的卡留在 retry 佇列，等下次使用者主動「捏肉球」才作為複習卡穿插出現
- **不需新增 Notion 欄位**，純程式邏輯修正
- **改動位置**：`src/services/study_service.py` → `handle_card_not_sure()`
  - 修法 A（推薦）：`send_next_card()` 加 `skip_retry=True` 參數，有傳入時強制走新卡邏輯（`current_index + 1`）
  - 修法 B：`handle_card_not_sure()` 直接取 `current_index + 1` 發新卡，不呼叫 `send_next_card()`
- **注意**：若目前正在複習的是 retry 卡（`is_retry=True`），點「還不熟」後應重新 add_retry 並跳到下一張 retry 或新卡（同修法 A 邏輯）

## Learning Card DB 擴充架構（待實作）

### iPAS 考試結構
- **初級**：科目一 + 科目二 均為必考，用戶一起讀，Card_ID 全局流水號，`Exam_Type = 初級`
- **中級**：科目一/二/三，用戶**選考**（通常考 1~2 科，也可跨梯次），每科需獨立進度追蹤

### 未來擴充步驟（安全順序，不影響現有用戶）
1. Notion Learning Card DB 加 `Exam_Type` Select 欄位（初級/中級）
2. 把所有現有卡片標記為 `Exam_Type = 初級`（步驟 1、2 不動程式碼，對用戶零影響）
3. 部署程式碼：`get_learning_card(index, exam_type)` 加 `Exam_Type` 過濾
4. 中級上線時：加 `Subject` Select 過濾（科目一/二/三）+ User Progress DB 改為支援一人多科進度

### 注意事項
- 步驟 2 必須在步驟 3 **之前**完成，否則過濾後取不到卡片，影響 50+ 現有用戶
- Learning Card DB 已有 `Subject` Select 欄位（目前程式碼未使用）
- 現行程式碼只查 `Card_ID`，新增 Notion 欄位對現有功能完全無影響
