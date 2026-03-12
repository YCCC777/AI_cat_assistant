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
│   ├── notion_service.py   # Notion API (課程DB + 陪讀進度DB + 學習卡DB + 刷題DB)
│   ├── study_service.py    # 陪讀模組業務邏輯
│   └── quiz_service.py     # 刷題模組業務邏輯（餵罐罐）⚠️ 尚未部署
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
| `捏肉球` | 今天第一次 → 打卡儀式（連續天數 + 倒數 + 社群人數）；已打卡 → 直接發學習卡 |
| `餵罐罐` / `刷題` | 刷題系統入口 → 選科 → 50題隨機 pool → 作答 loop → 成績報告 ⚠️ 尚未部署 |
| `結束刷題` | 中途結束刷題，顯示本場成績 ⚠️ 尚未部署 |
| `讀書進度` | 顯示進度 + 倒數 + 連續打卡天數 + 已達成稱號 |
| `貓咪陪讀` | 顯示陪讀 carousel（3張卡） |
| `報名` / `陪讀設定` | 兩層 Quick Reply 選單（考試種類 → 日期），**不接受文字格式** |
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
NOTION_QUIZ_DB_ID=               # 刷題題庫 DB（已建立，⚠️ 尚未部署）
NOTION_QUIZ_PROGRESS_DB_ID=      # 刷題用戶進度 DB（已建立，⚠️ 尚未部署）
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
| 2026-03-11 | 捏肉球改為每日打卡儀式入口：第一次顯示 streak + 倒數 + 社群人數，已打卡直接發學習卡 |
| 2026-03-11 | 學習卡移除倒數顯示（倒數只在打卡訊息出現） |
| 2026-03-11 | Learning Card DB 加 Exam_Type 過濾，防止初級/中級卡混用 |
| 2026-03-11 | 文字格式「報名 xxx」改導向按鈕選單，不再接受文字報名 |
| 2026-03-11 | 互助激勵系統上線：稱號（動態計算）、里程碑慶祝 push、社群打卡人數、進度提示 |
| 2026-03-11 | 餵罐罐刷題系統設計完成（quiz_service.py 新建）⚠️ 尚未部署，等題庫準備好後推送 |

## 已知待改項目

（目前無待修復 Bug）

## 刷題系統（餵罐罐）⚠️ 尚未部署

### 部署前檢查清單
- [ ] 初級題庫填入 Quiz_DB（考古題 + 樣題優先）
- [ ] 確認 User_Progress_DB 中無中級報名記錄（避免未潤的中級學習卡流出）
- [ ] 部署後測試：傳「餵罐罐」→ 選科 → 作答 → 對錯回饋 → 下一題 → 50題成績
- [ ] 部署後測試：答案開獎後點「⚠️ 回報問題」→ 輸入意見 → 管理員收到通知

### Quiz_DB 欄位規格
| 欄位 | 類型 | 說明 |
|------|------|------|
| `Question_ID` | Title | `Q001`, `Q002`... |
| `Exam_Type` | Select | `iPAS AI應用規劃師(初級)` / `iPAS AI應用規劃師(中級)` |
| `Subject` | Select | `科目一` / `科目二` / `科目三` |
| `Chapter` | Rich Text | 章節名稱 |
| `Source` | Select | `考古題` / `114考古題` / `官方樣題` / `AI生成` / `資深考官專家題` |
| `Question` | Rich Text | 題目內容 |
| `Option_A` ~ `Option_D` | Rich Text | 四個選項 |
| `Correct_Answer` | Select | `A` / `B` / `C` / `D` |
| `Explanation` | Rich Text | 解說（為何對 + 為何其他選項錯）|

### Quiz_Progress_DB 欄位規格
| 欄位 | 類型 | 說明 |
|------|------|------|
| `User_ID` | Title | LINE User ID |
| `Exam_Type` | Rich Text | 隔離初級/中級進度 |
| `Total_Answered` | Number | 累計答題數 |
| `Correct_Count` | Number | 累計答對數 |
| `Wrong_Queue` | Rich Text | JSON，上一輪錯題（必出，max 20）|
| `Answered_IDs` | Rich Text | JSON，已答過的題 |
| `Selected_Subjects` | Rich Text | JSON，中級選考科目（初級留空）|

### 刷題流程說明
- 每輪 50 題，開始時一次組建 pool（上一輪錯題全含 + 隨機補齊）
- 初級：固定選科（科目一 / 科目二），開始前顯示選科 Quick Reply
- 中級：選考科目來自 `Quiz_Progress_DB.Selected_Subjects`，顯示對應科目按鈕
- 答錯 → 記入 Wrong_Queue，**下一輪**才出現（不在當下這輪重出）
- 刷滿 50 題 → 自動顯示成績報告；中途可傳「結束刷題」
- 答案開獎後可點「⚠️ 回報問題」→ 寫入 `NOTION_REPORT_DB_ID`（與學習卡回報共用）+ push 通知管理員
  - `Card_ID` 欄位存題目編號字串（e.g. `Q003`），可與學習卡回報（數字）區分

### 中級上線 Checklist（程式碼已備好，補資料即可）
- [ ] Quiz_DB 填入中級各科題目（`Subject` 欄位標記）
- [ ] 報名流程加「選科」步驟，寫入 `Quiz_Progress_DB.Selected_Subjects`
- [ ] 中級學習卡潤稿完成

## Learning Card DB 擴充架構

### iPAS 考試結構
- **初級**：科目一 + 科目二 均為必考，Card_ID 全局流水號，`Exam_Type = iPAS AI應用規劃師(初級)`
- **中級**：科目一/二/三，用戶**選考**，每科需獨立進度追蹤，`Exam_Type = iPAS AI應用規劃師(中級)`

### 擴充步驟狀態
1. ✅ Learning Card DB 加 `Exam_Type` Select 欄位（已完成 2026-03-11）
2. ✅ 現有初級卡片標記 `Exam_Type = iPAS AI應用規劃師(初級)`（已完成 2026-03-11）
3. ✅ 程式碼加 `Exam_Type` 過濾（已部署 2026-03-11）
4. ⏳ 中級上線時：加 `Subject` Select 過濾（科目一/二/三）+ User Progress DB 改為支援一人多科進度

### 注意事項
- Select 值為半形括號：`iPAS AI應用規劃師(初級)` / `iPAS AI應用規劃師(中級)`
- Learning Card DB 已有 `Subject` Select 欄位（程式碼目前未使用，保留供中級擴充）
- 中級科目二學習卡準備中（2026-03-11）

## Notion User Progress DB 欄位一覽

| 欄位 | 類型 | 說明 |
|------|------|------|
| `User_ID` | Title | LINE User ID |
| `Exam_Name` | Rich Text | 考試名稱 |
| `Exam_Date` | Date | 考試日期 |
| `Current_Card_Index` | Number | 當前進度索引 |
| `Understood_Count` | Number | 已懂張數 |
| `Not_Sure_Count` | Number | 不熟張數 |
| `Retry_Indices` | Rich Text | 複習佇列 JSON `[1,5,12]` |
| `Last_Check_In_Date` | Date | 最後打卡日期（判斷每日第一次） |
| `Streak_Days` | Number | 連續打卡天數 |
| `Last_Interaction` | Date | 最後互動時間（自動更新） |

## 互助激勵系統說明

稱號與里程碑定義在 `src/services/study_service.py` 頂部常數，**不需要 Notion 欄位，動態計算**：

| 條件 | 稱號 |
|------|------|
| 連續打卡 3 天 | 🐾 肉球新鮮人 |
| 連續打卡 7 天 | ⭐ 週週精進 |
| 連續打卡 30 天 | 🔥 燃燒的肉球 |
| 已懂 10 張 | 📖 初探知識海 |
| 已懂 30 張 | 📚 知識旅人 |
| 已懂 50 張 | 🎯 半程勇者 |
