FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY VERSION ./
COPY app ./app
COPY slie ./slie
COPY docs ./docs
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --upgrade pip && pip install . && pip install aiosqlite

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]
