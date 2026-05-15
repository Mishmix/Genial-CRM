"""Slow but reliable migration - commit after each row."""
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:gDykzhbPADwepWIMVBZVcAUWYPZmvlxv@ballast.proxy.rlwy.net:40590/railway"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

log("Connecting...")
sq = create_engine(SQLITE_URL).connect()
pg_engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
Session = sessionmaker(bind=pg_engine)

# Check current state
pg = pg_engine.connect()
try:
    clients_count = pg.execute(text("SELECT COUNT(*) FROM clients")).scalar()
    log(f"Current clients in PG: {clients_count}")
except:
    clients_count = 0
    log("Tables don't exist, will create")
pg.close()

# Create tables if needed
if clients_count == 0:
    log("Creating tables...")
    sys.path.insert(0, '.')
    from app.models import Base
    Base.metadata.create_all(bind=pg_engine)
    log("Tables ready!")

# Get unique clients from SQLite
log("Getting unique clients from SQLite...")
result = sq.execute(text("""
    SELECT * FROM clients 
    WHERE id IN (SELECT MIN(id) FROM clients GROUP BY telegram_user_id)
    ORDER BY id
"""))
rows = result.fetchall()
cols = list(result.keys())
log(f"Found {len(rows)} unique clients")

# Get already migrated IDs
pg = pg_engine.connect()
existing = set(r[0] for r in pg.execute(text("SELECT telegram_user_id FROM clients")).fetchall())
pg.close()
log(f"Already in PG: {len(existing)}")

# Boolean columns
BOOL = ["thumbnail_processed", "owner_replied", "is_archived"]

# Migrate one by one
done = 0
skipped = 0
errors = 0

for i, row in enumerate(rows):
    data = dict(zip(cols, row))
    
    # Skip if already exists
    if data["telegram_user_id"] in existing:
        skipped += 1
        continue
    
    # Fix booleans
    for c in BOOL:
        if c in data and data[c] is not None:
            data[c] = bool(data[c])
    
    # Insert with new connection each time (slow but reliable)
    session = Session()
    try:
        c = ", ".join([f'"{k}"' for k in data.keys()])
        v = ", ".join([f":{k}" for k in data.keys()])
        session.execute(text(f'INSERT INTO clients ({c}) VALUES ({v})'), data)
        session.commit()
        done += 1
        existing.add(data["telegram_user_id"])
    except Exception as e:
        session.rollback()
        errors += 1
    finally:
        session.close()
    
    if (i + 1) % 10 == 0:
        log(f"Progress: {done} done, {skipped} skipped, {errors} errors (total {i+1}/{len(rows)})")

log(f"CLIENTS DONE: {done} migrated, {skipped} skipped, {errors} errors")

# Reset sequence
pg = pg_engine.connect()
try:
    m = pg.execute(text("SELECT MAX(id) FROM clients")).scalar()
    if m:
        pg.execute(text(f"SELECT setval('clients_id_seq', {m})"))
        pg.commit()
except:
    pass
pg.close()

sq.close()
log("Done!")
