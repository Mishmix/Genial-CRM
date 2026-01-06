"""Clean migration - handles duplicates properly."""
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:gDykzhbPADwepWIMVBZVcAUWYPZmvlxv@ballast.proxy.rlwy.net:40590/railway"

BATCH = 100

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

log("Connecting...")
sq = create_engine(SQLITE_URL).connect()
pg = create_engine(POSTGRES_URL, pool_pre_ping=True, pool_timeout=60).connect()

# Drop ALL and recreate
log("Dropping ALL tables...")
pg.execute(text("DROP SCHEMA public CASCADE"))
pg.execute(text("CREATE SCHEMA public"))
pg.commit()

log("Creating tables...")
sys.path.insert(0, '.')
from app.models import Base
Base.metadata.create_all(bind=pg.engine)
log("Tables created!")

# Boolean columns
BOOL = {
    "templates": ["is_auto_reply", "is_active"],
    "clients": ["thumbnail_processed", "owner_replied", "is_archived"],
    "orders": ["has_ab_test", "has_title", "has_rush"],
    "conversations": ["is_deleted", "auto_reply_sent", "owner_replied"],
    "reminders": ["is_sent", "is_completed"],
}

def fix(t, d):
    if t in BOOL:
        for c in BOOL[t]:
            if c in d and d[c] is not None:
                d[c] = bool(d[c])
    return d

# Migrate tables
tables = [
    ("settings", "key"),  # primary key column
    ("admins", "id"),
    ("tags", "id"),
    ("templates", "id"),
    ("rejection_reasons", "id"),
    ("clients", "id"),  # Will handle telegram_user_id duplicates
    ("client_aliases", "id"),
    ("client_tags", None),  # composite key
    ("conversations", "id"),
    ("messages", "id"),
    ("orders", "id"),
    ("reminders", "id"),
    ("sessions", "id"),
    ("daily_stats", "date"),
]

for t, pk in tables:
    try:
        # For clients, get unique by telegram_user_id (keep first)
        if t == "clients":
            query = """
                SELECT * FROM clients 
                WHERE id IN (
                    SELECT MIN(id) FROM clients GROUP BY telegram_user_id
                )
            """
        else:
            query = f"SELECT * FROM {t}"
        
        result = sq.execute(text(query))
        rows = result.fetchall()
        cols = list(result.keys())
        
        if not rows:
            log(f"{t}: empty")
            continue
        
        cnt = len(rows)
        done = 0
        
        for i in range(0, cnt, BATCH):
            batch = rows[i:i+BATCH]
            for r in batch:
                d = fix(t, dict(zip(cols, r)))
                c = ", ".join([f'"{k}"' for k in d.keys()])
                v = ", ".join([f":{k}" for k in d.keys()])
                try:
                    pg.execute(text(f'INSERT INTO {t} ({c}) VALUES ({v})'), d)
                    done += 1
                except Exception as e:
                    pg.rollback()
            pg.commit()
            log(f"{t}: {done}/{cnt}")
        
        # Reset sequence
        if pk and pk == "id":
            try:
                m = pg.execute(text(f"SELECT MAX(id) FROM {t}")).scalar()
                if m:
                    pg.execute(text(f"SELECT setval('{t}_id_seq', {m})"))
                    pg.commit()
            except:
                pass
                
    except Exception as e:
        log(f"{t}: ERROR - {str(e)[:100]}")

log("MIGRATION COMPLETE!")
sq.close()
pg.close()
