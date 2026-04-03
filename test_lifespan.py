import asyncio
from app.main import lifespan, app

async def test():
    async with lifespan(app):
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test())
