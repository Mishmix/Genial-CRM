"""Check PostgreSQL tables."""
from sqlalchemy import create_engine, text

POSTGRES_URL = "postgresql://postgres:AJTHvKxErblWKUfANfeCPXpBSoOOxMBF@switchyard.proxy.rlwy.net:44751/railway"

engine = create_engine(POSTGRES_URL)
conn = engine.connect()

# Check tables
result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
tables = [r[0] for r in result]
print(f"Tables: {tables}")

# Check clients column type
if 'clients' in tables:
    result = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='clients' AND column_name='telegram_user_id'
    """))
    for r in result:
        print(f"clients.telegram_user_id type: {r[1]}")
    
    # Count rows
    result = conn.execute(text("SELECT COUNT(*) FROM clients"))
    print(f"Clients count: {result.scalar()}")

conn.close()
