"""Check migration progress."""
from sqlalchemy import create_engine, text

POSTGRES_URL = "postgresql://postgres:gDykzhbPADwepWIMVBZVcAUWYPZmvlxv@ballast.proxy.rlwy.net:40590/railway"

pg = create_engine(POSTGRES_URL).connect()

tables = ["settings", "admins", "tags", "templates", "rejection_reasons", 
          "clients", "conversations", "messages", "orders", "reminders"]

print("PostgreSQL counts:")
for t in tables:
    try:
        cnt = pg.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        print(f"  {t}: {cnt}")
    except Exception as e:
        print(f"  {t}: error")

pg.close()
