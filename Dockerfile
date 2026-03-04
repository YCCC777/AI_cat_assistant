# 使用官方 Python 輕量版
FROM python:3.12-slim

# 設定工作目錄
WORKDIR /app

# 安裝 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 複製依賴文件並安裝
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# 複製所有原始碼 (排除 .env 與 credentials)
COPY src ./src
COPY README.md ./

# 建立必要的資料夾 (用於存放 json 紀錄)
RUN mkdir -p /app/data
# 修正 token_usage.json 與 user_usage.json 的路徑 (後續我們會微調程式碼讀取這裡)

# 設定環境變數
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# 暴露 Hugging Face 預設端口
EXPOSE 7860

# 啟動指令 (使用 uv 執行)
CMD ["uv", "run", "python", "-m", "src.main"]
