# Stage 1: builder
FROM python:3.10-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Stage 2: runtime
FROM python:3.10-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "src.food11.serve:app", "--host", "0.0.0.0", "--port", "8000"]