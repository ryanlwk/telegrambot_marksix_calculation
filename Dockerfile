# 使用輕量化映像檔作為地基
FROM python:3.12-slim

# 安裝 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 關鍵：安裝 Matplotlib 繪圖所需的系統依賴
# 這些在庫 (libraries) 是生成圖表圖片的必備組件
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpng-dev \
    libfreetype6-dev \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 利用 uv 的緩存機制，先安裝依賴
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 複製應用程式代碼
COPY . .

# 設定環境變數
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 健康檢查 - 確保 python 進程還活著
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD pgrep -f "python" || exit 1

# 啟動機器人
CMD ["uv", "run", "agentbot.py"]