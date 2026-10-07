import asyncio
from app.memory.cloud_sql import engine
from sqlalchemy import text

async def check_tables():
    print("🔍 Vérification des tables dans Cloud SQL...\n")
    async with engine.connect() as conn:
        # Requête pour lister toutes les tables du schéma public
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """
        result = await conn.execute(text(query))
        tables = result.fetchall()

        print(f"✅ {len(tables)} table(s) trouvée(s) dans la base 'luckyjet' :")
        for table in tables:
            print(f"   📊 {table[0]}")

if __name__ == "__main__":
    asyncio.run(check_tables())