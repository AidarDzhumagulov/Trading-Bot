# Backend - DCA Trading Bot

Backend API на FastAPI + SQLAlchemy + PostgreSQL.

## Установка

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Миграции

```bash
alembic revision --autogenerate -m "описание"
alembic upgrade head
```

## Запуск

```bash
uvicorn main:app --reload --port 8070
```

Или через Docker:

```bash
docker-compose up
```

## Структура

- `app/core/` - конфигурация и зависимости
- `app/infrastructure/` - модели БД
- `app/domain/` - бизнес-логика
- `app/presentation/` - API роутеры
- `app/shared/` - общие утилиты

## Технологии

- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- Alembic
- ccxt
