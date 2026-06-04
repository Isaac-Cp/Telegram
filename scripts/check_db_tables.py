from sqlalchemy import create_engine, inspect
from app.core.config import get_settings, normalize_database_url

settings = get_settings()
db_url = normalize_database_url(settings.sqlalchemy_database_url).replace("postgresql+asyncpg", "postgresql+psycopg")

try:
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables found: {tables}")
    if "apscheduler_jobs" in tables:
        print("apscheduler_jobs table exists.")
    else:
        print("apscheduler_jobs table NOT found.")
except Exception as e:
    print(f"Error: {e}")
