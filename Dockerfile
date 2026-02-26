FROM python:3.12-slim-bookworm

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files and install
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"

# Health check - verify bot process is running
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD pgrep -f "agentbot.py" || exit 1

# Start the bot
CMD ["uv", "run", "agentbot.py"]