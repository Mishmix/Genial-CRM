"""Migrate data only (tables already exist with BIGINT)."""
import sys
from sqlalchemy import create_engine, text

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:AJTHvKxErblWKUfANfeCPXpBSoOOxMBF@switchyard.proxy.rlwy.net:44751/railway"

TABLES = [
    "settings", "admins", "tags", "templates", "rejection_reasons",
    "clients", "client_aliases", "client_tags", "conversations",
    "messages", "orders", "reminders", "sessions", "daily_stats",
]

BOOLEAN_COLUMNS = {
    "templates": ["is_auto_reply", "is_active"],
    "clients": ["thumbnail_processed", "owner_replied", "is_archived"],
    "orders": ["has_ab_test", "has_title", "has_rush"],
    "conversations": ["is_deleted", "auto_reply_sent", "owner_replied"],
    "reminders": ["is_sent", "is_completed"],
}

def convert_booleans(table_name, data):
    if table_name in BOOLEAN_COLUMNS:
        for col in BOOLEAN_COLUMNS[table_name]:
            if col in data and data[col] is not None:
                data[col] = bool(data[col])
    return data

print("Connecting to SQLite...", flush=True)
sqlite_engine = create_engine(SQLITE_URL)
sqlite_conn = sqlite_engine.connect()

print("Connecting to PostgreSQL...", flush=True)
pg_engine = create_engine(POSTGRES_URL)
pg_conn = pg_engine.connect()

# Clear existing data
print("Clearing existing data...", flush=True)
for t in reversed(TABLES):
    try:
        pg_conn.execute(text(f"DELETE FROM {t}"))
        pg_conn.commit()
    except:
        pg_conn.rollback()

# Migrate each table
for table_name in TABLES:
    try:
        result = sqlite_conn.execute(text(f"SELECT * FROM {table_name}"))
        rows = result.fetchall()
        columns = list(result.keys())
        
        if not rows:
            print(f"  {table_name}: empty", flush=True)
            continue
        
        count = 0
        errors = 0
        for row in rows:
            data = dict(zip(columns, row))
            data = convert_booleans(table_name, data)
            
            cols = ", ".join([f'"{k}"' for k in data.keys()])
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            try:
                pg_conn.execute(text(f'INSERT INTO {table_name} ({cols}) VALUES ({placeholders})'), data)
                count += 1
            except Exception as e:
                errors += 1
                pg_conn.rollback()
        
        pg_conn.commit()
        err_str = f" ({errors} errors)" if errors else ""
        print(f"  {table_name}: {count}/{len(rows)}{err_str}", flush=True)
        
    except Exception as e:
        print(f"  {table_name}: ERROR - {str(e)[:60]}", flush=True)
        pg_conn.rollback()

# Reset sequences
print("Resetting sequences...", flush=True)
for t in ["admins", "tags", "templates", "rejection_reasons", "clients", 
          "client_aliases", "conversations", "messages", "orders", "reminders", "sessions"]:
    try:
        r = pg_conn.execute(text(f"SELECT MAX(id) FROM {t}"))
        m = r.scalar()
        if m:
            pg_conn.execute(text(f"SELECT setval('{t}_id_seq', {m})"))
            pg_conn.commit()
    except:
        pass

print("Done!", flush=True)
sqlite_conn.close()
pg_conn.close()
