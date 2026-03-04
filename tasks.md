# 🐱 貓咪助手開發進度追蹤表 (Task List)

## 📌 Phase 1: 基礎架構與核心解析 (已完成 ✅)
- [x] 初始化 uv 專案結構與環境設定
- [x] 重複訊息攔截器 (`deduplicator.py`)
- [x] 基礎 Token 額度限制器 (`limiter.py`)
- [x] Gemini 2.5 Flash Lite 課程解析邏輯
- [x] Google Calendar & Notion 基礎同步
- [x] LINE Persona 設定 (傲嬌貓咪語氣)

---

## 🚀 Phase 2: 陪讀模組與核心互動架構 (已完成 ✅)

### 2.1 Notion 資料結構擴充 (已完成 ✅)
- [x] 在 Notion 建立「使用者進度表」(`User_ID`, `Exam_Name`, `Exam_Date`, `Current_Card_Index`, `Last_Interaction`)
- [x] 在 Notion 建立「學習卡圖書館」(`Card_ID`, `Chapter`, `Content`)
- [x] 擴展 `notion_service.py`：新增讀取/更新使用者進度邏輯
- [x] 擴展 `notion_service.py`：獲獲指定 Index 的學習卡內容

### 2.2 陪讀模組邏輯實作 (已完成 ✅)
- [x] **報名流程**：實作解析使用者輸入的考試資訊 (名稱與日期) 並寫入 Notion
- [x] **餵罐罐 (Learning Card)**：發送學習卡並附帶 `Postback Action` 按鈕「喵～我懂了」
- [x] **捏肉球 (Countdown)**：實作考試倒數計算與鼓勵訊息
- [x] **讀書進度**：查詢並回報已讀卡片總量

### 2.3 LINE UI/UX 升級 (已完成 ✅)
- [x] **Rich Menu 部署**：設定底層圖文選單 (引導至關鍵字觸發)
- [x] **Carousel Menu**：實作點擊「貓咪陪讀專區」後彈出的橫向輪播選單
- [x] **Persona 語氣校準**：優化報錯與引導台詞，強化貓咪個性

### 2.4 防擠兌與效能優化 (已完成 ✅)
- [x] **限流機制升級**：完善 `user_limiter.py`，加入 3 秒頻率限制 (is_too_fast)
- [x] **優雅降級**：當 API 擁塞時回覆貓咪專屬的「忙碌中」訊息

---

## 🌟 Phase 3: AI 週報與社群共建模組 (待啟動 🚀)

### 3.1 RSS 抓取與 AI 摘要 (Automation)
- [ ] **RSS Service**：建立定時抓取 RSS Feed (iThome 等) 的功能
- [ ] **Gemini 週報加工**：使用 AI 潤飾摘要成「貓咪視角」週報
- [ ] **週報存儲**：同步至 Notion 週報資料庫

### 3.2 社群投稿機制 (Community)
- [ ] **指令解析器**：實作 `/收錄 [URL]` 解析邏輯
- [ ] **投稿流程**：將網址寫入 Notion「待審核區」
- [ ] **投稿限額**：實作每人每日投稿次數限制

---

## 🛠️ 維護與優化
- [ ] **錯誤監控**：紀錄 API 失敗率與 Token 消耗量
- [ ] **部署更新**：確保 Render/Hugging Face 部署流程自動化
