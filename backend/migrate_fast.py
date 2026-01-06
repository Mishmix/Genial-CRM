"""Fast migration - single connection, batch inserts."""
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:gDykzhbPADwepWIMVBZVcAUWYPZmvlxv@ballast.proxy.rlwy.net:40590/railway"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

log("Connecting...")
sq = create_engine(SQLITE_URL).connect()
pg = create_engine(POSTGRES_URL, pool_pre_ping=True).connect()

# Get client mappings
log("Getting client mappings...")
pg_clients = {r[0]: r[1] for r in pg.execute(text("SELECT telegram_user_id, id FROM clients")).fetchall()}
sq_client_map = {r[0]: r[1] for r in sq.execute(text("SELECT id, telegram_user_id FROM clients")).fetchall()}
log(f"PG clients: {len(pg_clients)}")

# ============ CONVERSATIONS ============
log("\n=== CONVERSATIONS ===")
convs = sq.execute(text("SELECT * FROM conversations")).fetchall()
conv_cols = list(sq.execute(text("SELECT * FROM conversations LIMIT 1")).keys())
existing = set(r[0] for r in pg.execute(text("SELECT id FROM conversations")).fetchall())

done = 0
for row in convs:
    data = dict(zip(conv_cols, row))
    if data["id"] in existing:
        continue
    tg_id = sq_client_map.get(data["client_id"])
    if not tg_id or tg_id not in pg_clients:
        continue
    data["client_id"] = pg_clients[tg_id]
    for c in ["is_deleted", "auto_reply_sent", "owner_replied"]:
        if data.get(c) is not None: data[c] = bool(data[c])
    try:
        c = ", ".join([f'"{k}"' for k in data.keys()])
        v = ", ".join([f":{k}" for k in data.keys()])
        pg.execute(text(f'INSERT INTO conversations ({c}) VALUES ({v})'), data)
        done += 1
    except:
        pg.rollback()
pg.commit()
log(f"Conversations: {done} done")

# ============ MESSAGES (last 10 per client) ============
log("\n=== MESSAGES ===")
msg_query = """
    SELECT * FROM messages WHERE id IN (
        SELECT id FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY sent_at DESC) as rn
            FROM messages
        ) WHERE rn <= 10
    )
"""
messages = sq.execute(text(msg_query)).fetchall()
msg_cols = list(sq.execute(text("SELECT * FROM messages LIMIT 1")).keys())
existing = set(r[0] for r in pg.execute(text("SELECT id FROM messages")).fetchall())
log(f"Messages to migrate: {len(messages)}, existing: {len(existing)}")

done = 0
batch = []
for i, row in enumerate(messages):
    data = dict(zip(msg_cols, row))
    if data["id"] in existing:
        continue
    tg_id = sq_client_map.get(data["client_id"])
    if not tg_id or tg_id not in pg_clients:
        continue
    data["client_id"] = pg_clients[tg_id]
    data["conversation_id"] = None
    
    try:
        c = ", ".join([f'"{k}"' for k in data.keys()])
        v = ", ".join([f":{k}" for k in data.keys()])
        pg.execute(text(f'INSERT INTO messages ({c}) VALUES ({v})'), data)
        done += 1
        if done % 100 == 0:
            pg.commit()
            log(f"Messages: {done} done")
    except:
        pg.rollback()

pg.commit()
log(f"Messages: {done} total")

# ============ ORDERS ============
log("\n=== ORDERS ===")
orders = sq.execute(text("SELECT * FROM orders")).fetchall()
if orders:
    order_cols = list(sq.execute(text("SELECT * FROM orders LIMIT 1")).keys())
    existing = set(r[0] for r in pg.execute(text("SELECT id FROM orders")).fetchall())
    done = 0
    for row in orders:
        data = dict(zip(order_cols, row))
        if data["id"] in existing:
            continue
        tg_id = sq_client_map.get(data["client_id"])
        if not tg_id or tg_id not in pg_clients:
            continue
        data["client_id"] = pg_clients[tg_id]
        data["conversation_id"] = None
        for c in ["has_ab_test", "has_title", "has_rush"]:
            if data.get(c) is not None: data[c] = bool(data[c])
        try:
            c = ", ".join([f'"{k}"' for k in data.keys()])
            v = ", ".join([f":{k}" for k in data.keys()])
            pg.execute(text(f'INSERT INTO orders ({c}) VALUES ({v})'), data)
            done += 1
        except:
            pg.rollback()
    pg.commit()
    log(f"Orders: {done} done")
else:
    log("No orders")

# ============ REMINDERS ============
log("\n=== REMINDERS ===")
reminders = sq.execute(text("SELECT * FROM reminders")).fetchall()
if reminders:
    rem_cols = list(sq.execute(text("SELECT * FROM reminders LIMIT 1")).keys())
    existing = set(r[0] for r in pg.execute(text("SELECT id FROM reminders")).fetchall())
    done = 0
    for row in reminders:
        data = dict(zip(rem_cols, row))
        if data["id"] in existing:
            continue
        tg_id = sq_client_map.get(data["client_id"])
        if not tg_id or tg_id not in pg_clients:
            continue
        data["client_id"] = pg_clients[tg_id]
        data["conversation_id"] = None
        for c in ["is_sent", "is_completed"]:
            if data.get(c) is not None: data[c] = bool(data[c])
        try:
            c = ", ".join([f'"{k}"' for k in data.keys()])
            v = ", ".join([f":{k}" for k in data.keys()])
            pg.execute(text(f'INSERT INTO reminders ({c}) VALUES ({v})'), data)
            done += 1
        except:
            pg.rollback()
    pg.commit()
    log(f"Reminders: {done} done")
else:
    log("No reminders")

# Reset sequences
log("\nResetting sequences...")
for t in ["conversations", "messages", "orders", "reminders"]:
    try:
        m = pg.execute(text(f"SELECT MAX(id) FROM {t}")).scalar()
        if m: pg.execute(text(f"SELECT setval('{t}_id_seq', {m})"))
    except: pass
pg.commit()

sq.close()
pg.close()
log("\n=== DONE! ===")
