import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

async def test_db():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/slie_db")
    print(f"Testing DB: {db_url}")
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            print("PostgreSQL connection successful")
    except Exception as e:
        print(f"PostgreSQL connection failed: {e}")
    finally:
        await engine.dispose()

async def test_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Testing Redis: {redis_url}")
    try:
        client = redis.from_url(redis_url)
        await client.ping()
        print("Redis connection successful")
        await client.close()
    except Exception as e:
        print(f"Redis connection failed: {e}")

async def main():
    await test_db()
    await test_redis()

if __name__ == "__main__":
    asyncio.run(main())
