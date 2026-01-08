FROM python:3.12-slim
LABEL authors="aidardzumagulov"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir uv \
    && uv sync

COPY . .

ENV PYTHONPATH=/app

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8070"]
