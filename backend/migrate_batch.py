"""Migrate SQLite to PostgreSQL in batches with progress."""
import sys
from sqlalchemy import create_engine, text

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:hEQnVgkPtOjvoJicrYXpnjfmHGkADKab@ballast.proxy.rlwy.net:32607/railway"

BATCH_SIZE = 100

BOOL_COLS = {
    "templates": ["is_auto_reply", "is_active"],
    "clients": ["thumbnail_processed", "owner_replied", "is_archived"],
    "orders": ["has_ab_test", "has_title", "has_rush"],
    "conversations": ["is_deleted", "auto_reply_sent", "owner_replied"],
    "reminders": ["is_sent", "is_completed"],
}

def fix_bools(table, data):
    if table in BOOL_COLS:
        for c in BOOL_COLS[table]:
            if c in data and data[c] is not None:
                data[c] = bool(data[c])
    return data

print("Connecting...", flush=True)
sqlite = create_engine(SQLITE_URL).connect()
pg = create_engine(POSTGRES_URL).connect()

# Tables in order
tables = ["clients", "client_aliases", "client_tags", "conversations", "messages", "orders", "reminders", "sessions", "daily_stats"]

for table in tables:
    try:
        # Count
        cnt = sqlite.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        if cnt == 0:
            print(f"{table}: empty", flush=True)
            continue
        
        print(f"{table}: {cnt} rows...", flush=True)
        
        # Get columns
        result = sqlite.execute(text(f"SELECT * FROM {table} LIMIT 1"))
        cols = list(result.keys())
        
        # Migrate in batches
        done = 0
        errors = 0
        offset = 0
        
        while offset < cnt:
            rows = sqlite.execute(text(f"SELECT * FROM {table} LIMIT {BATCH_SIZE} OFFSET {offset}")).fetchall()
            
            for row in rows:
                data = fix_bools(table, dict(zip(cols, row)))
                col_str = ", ".join([f'"{k}"' for k in data.keys()])
                val_str = ", ".join([f":{k}" for k in data.keys()])
                try:
                    pg.execute(text(f'INSERT INTO {table} ({col_str}) VALUES ({val_str})'), data)
                    done += 1
                except Exception as e:
                    errors += 1
                    pg.rollback()
            
            pg.commit()
            offset += BATCH_SIZE
            pct = min(100, int(offset / cnt * 100))
            print(f"  {pct}% ({done}/{cnt})", flush=True)
        
        # Reset sequence
        try:
            max_id = pg.execute(text(f"SELECT MAX(id) FROM {table}")).scalar()
            if max_id:
                pg.execute(text(f"SELECT setval('{table}_id_seq', {max_id})"))
                pg.commit()
        except:
            pass
        
        err = f" ({errors} errors)" if errors else ""
        print(f"  Done: {done}{err}", flush=True)
        
    except Exception as e:
        print(f"{table}: ERROR - {e}", flush=True)

print("\nMigration complete!", flush=True)
sqlite.close()
pg.close()
