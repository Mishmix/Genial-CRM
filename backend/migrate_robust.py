"""Robust migration with auto-retry and reconnection."""
import sys
import time
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:gDykzhbPADwepWIMVBZVcAUWYPZmvlxv@ballast.proxy.rlwy.net:40590/railway"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_pg_session():
    """Create new PostgreSQL session."""
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True, connect_args={"connect_timeout": 30})
    return sessionmaker(bind=engine)()

def migrate_with_retry(table, query, cols_to_bool, unique_col=None, max_retries=5):
    """Migrate table with automatic retry on failure."""
    log(f"Starting {table}...")
    
    # Get data from SQLite
    sq = create_engine(SQLITE_URL).connect()
    result = sq.execute(text(query))
    rows = result.fetchall()
    cols = list(result.keys())
    sq.close()
    
    if not rows:
        log(f"{table}: empty")
        return
    
    log(f"{table}: {len(rows)} rows to migrate")
    
    # Get existing records
    existing = set()
    if unique_col:
        try:
            session = get_pg_session()
            existing = set(r[0] for r in session.execute(text(f"SELECT {unique_col} FROM {table}")).fetchall())
            session.close()
            log(f"{table}: {len(existing)} already in PG")
        except:
            pass
    
    done = 0
    skipped = 0
    errors = 0
    
    for i, row in enumerate(rows):
        data = dict(zip(cols, row))
        
        # Skip if exists
        if unique_col and data.get(unique_col) in existing:
            skipped += 1
            continue
        
        # Fix booleans
        for c in cols_to_bool:
            if c in data and data[c] is not None:
                data[c] = bool(data[c])
        
        # Try insert with retries
        success = False
        for attempt in range(max_retries):
            try:
                session = get_pg_session()
                c = ", ".join([f'"{k}"' for k in data.keys()])
                v = ", ".join([f":{k}" for k in data.keys()])
                session.execute(text(f'INSERT INTO {table} ({c}) VALUES ({v})'), data)
                session.commit()
                session.close()
                done += 1
                if unique_col:
                    existing.add(data.get(unique_col))
                success = True
                break
            except Exception as e:
                try:
                    session.close()
                except:
                    pass
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                else:
                    errors += 1
        
        if (i + 1) % 20 == 0:
            log(f"{table}: {done}/{len(rows)} done, {skipped} skip, {errors} err")
    
    log(f"{table} COMPLETE: {done} done, {skipped} skipped, {errors} errors")
    
    # Reset sequence
    if "id" in cols:
        try:
            session = get_pg_session()
            m = session.execute(text(f"SELECT MAX(id) FROM {table}")).scalar()
            if m:
                session.execute(text(f"SELECT setval('{table}_id_seq', {m})"))
                session.commit()
            session.close()
        except:
            pass

# Main migration
log("=== ROBUST MIGRATION START ===")

# 1. Clients (unique by telegram_user_id)
migrate_with_retry(
    "clients",
    "SELECT * FROM clients WHERE id IN (SELECT MIN(id) FROM clients GROUP BY telegram_user_id) ORDER BY id",
    ["thumbnail_processed", "owner_replied", "is_archived"],
    "telegram_user_id"
)

# 2. Conversations
migrate_with_retry(
    "conversations",
    "SELECT * FROM conversations ORDER BY id",
    ["is_deleted", "auto_reply_sent", "owner_replied"],
    "id"
)

# 3. Messages
migrate_with_retry(
    "messages",
    "SELECT * FROM messages ORDER BY id",
    [],
    "id"
)

# 4. Orders
migrate_with_retry(
    "orders",
    "SELECT * FROM orders ORDER BY id",
    ["has_ab_test", "has_title", "has_rush"],
    "id"
)

# 5. Reminders
migrate_with_retry(
    "reminders",
    "SELECT * FROM reminders ORDER BY id",
    ["is_sent", "is_completed"],
    "id"
)

log("=== MIGRATION COMPLETE ===")
