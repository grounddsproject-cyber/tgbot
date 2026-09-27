import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres")

async def test():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Подключение к БД успешно!")
        print(f"PostgreSQL версия: {version}")
        
        # Проверяем таблицу servers
        servers = await conn.fetch("SELECT name, status FROM servers")
        print(f"\nСерверы в БД:")
        for s in servers:
            print(f"  - {s['name']}: статус {s['status']}")
        
        await conn.close()
    except Exception as e:
        print(f"❌ Ошибка подключения к БД:")
        print(f"{type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test())
