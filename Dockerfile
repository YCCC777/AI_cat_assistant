# 使用官方 Python 輕量版
FROM python:3.12-slim

# 設定工作目錄
WORKDIR /app

# 安裝 uv 與 curl
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# 複製依賴文件並安裝
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# 複製所有原始碼 (排除 .env 與 credentials)
COPY src ./src
COPY README.md ./

# 建立 image 資料夾並從 GitHub 下載 Rich Menu 圖片
# (圖片不 commit 進 HF Spaces，由 build 時自動抓取)
RUN mkdir -p /app/image && \
    curl -fsSL "https://raw.githubusercontent.com/YCCC777/AI_cat_assistant/main/image/rich_menu.jpg" \
    -o /app/image/rich_menu.jpg

# 設定環境變數
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# 暴露 Hugging Face 預設端口
EXPOSE 7860

# 啟動指令 (直接用 uvicorn，避免 python -m 雙重 import)
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]
