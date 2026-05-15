"""Full migration SQLite -> PostgreSQL with progress."""
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:gDykzhbPADwepWIMVBZVcAUWYPZmvlxv@ballast.proxy.rlwy.net:40590/railway"

BATCH = 50

BOOL_COLS = {
    "templates": ["is_auto_reply", "is_active"],
    "clients": ["thumbnail_processed", "owner_replied", "is_archived"],
    "orders": ["has_ab_test", "has_title", "has_rush"],
    "conversations": ["is_deleted", "auto_reply_sent", "owner_replied"],
    "reminders": ["is_sent", "is_completed"],
}

def fix(t, d):
    if t in BOOL_COLS:
        for c in BOOL_COLS[t]:
            if c in d and d[c] is not None:
                d[c] = bool(d[c])
    return d

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

log("Connecting...")
sq = create_engine(SQLITE_URL).connect()
pg = create_engine(POSTGRES_URL, pool_pre_ping=True).connect()

# Drop and recreate tables
log("Dropping tables...")
tables_rev = ["sessions", "reminders", "orders", "messages", "client_aliases", 
              "client_tags", "conversations", "clients", "daily_stats",
              "rejection_reasons", "templates", "tags", "admins", "settings"]
for t in tables_rev:
    try:
        pg.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE"))
        pg.commit()
    except:
        pg.rollback()

log("Creating tables...")
sys.path.insert(0, '.')
from app.models import Base
Base.metadata.create_all(bind=pg.engine)
log("Tables ready!")

tables = [
    "settings", "admins", "tags", "templates", "rejection_reasons",
    "clients", "client_aliases", "client_tags", "conversations", 
    "messages", "orders", "reminders", "sessions", "daily_stats"
]

for t in tables:
    try:
        cnt = sq.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        if cnt == 0:
            log(f"{t}: empty")
            continue
        
        cols = list(sq.execute(text(f"SELECT * FROM {t} LIMIT 1")).keys())
        
        done = 0
        errs = 0
        for off in range(0, cnt, BATCH):
            rows = sq.execute(text(f"SELECT * FROM {t} LIMIT {BATCH} OFFSET {off}")).fetchall()
            for r in rows:
                d = fix(t, dict(zip(cols, r)))
                c = ", ".join([f'"{k}"' for k in d.keys()])
                v = ", ".join([f":{k}" for k in d.keys()])
                try:
                    pg.execute(text(f'INSERT INTO {t} ({c}) VALUES ({v})'), d)
                    done += 1
                except:
                    errs += 1
                    pg.rollback()
            pg.commit()
            log(f"{t}: {done}/{cnt}" + (f" ({errs} err)" if errs else ""))
        
        # Reset sequence
        try:
            m = pg.execute(text(f"SELECT MAX(id) FROM {t}")).scalar()
            if m: 
                pg.execute(text(f"SELECT setval('{t}_id_seq', {m})"))
                pg.commit()
        except: 
            pass
        
    except Exception as e:
        log(f"{t}: ERROR {str(e)[:80]}")

log("DONE!")
sq.close()
pg.close()
