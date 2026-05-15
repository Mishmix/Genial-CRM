"""Reset PostgreSQL database - drop all tables."""
from sqlalchemy import create_engine, text

POSTGRES_URL = "postgresql://postgres:AJTHvKxErblWKUfANfeCPXpBSoOOxMBF@switchyard.proxy.rlwy.net:44751/railway"

print("Connecting...")
engine = create_engine(POSTGRES_URL, connect_args={"connect_timeout": 10})
conn = engine.connect()

print("Dropping schema...")
conn.execute(text("DROP SCHEMA public CASCADE"))
conn.execute(text("CREATE SCHEMA public"))
conn.commit()

print("Done! Tables will be recreated by backend on startup.")
conn.close()
