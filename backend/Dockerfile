FROM python:3.13-slim
LABEL authors="aidardzumagulov"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

ENV UV_PYTHON_PREFERENCE=only-system
ENV UV_SYSTEM_PYTHON=1
ENV UV_LINK_MODE=copy

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir uv \
    && uv sync

COPY . .

ENV PYTHONPATH=/app

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8070"]
