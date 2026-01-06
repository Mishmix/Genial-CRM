"""Migrate remaining data: conversations, last 10 messages per client, orders, reminders."""
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:gDykzhbPADwepWIMVBZVcAUWYPZmvlxv@ballast.proxy.rlwy.net:40590/railway"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def get_session():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True, connect_args={"connect_timeout": 30})
    return sessionmaker(bind=engine)()

log("Connecting to SQLite...")
sq = create_engine(SQLITE_URL).connect()

log("Getting migrated client IDs from PostgreSQL...")
session = get_session()
pg_clients = {r[0]: r[1] for r in session.execute(text("SELECT telegram_user_id, id FROM clients")).fetchall()}
session.close()
log(f"Found {len(pg_clients)} clients in PostgreSQL")

# Get SQLite client_id -> telegram_user_id mapping
sq_client_map = {r[0]: r[1] for r in sq.execute(text("SELECT id, telegram_user_id FROM clients")).fetchall()}

# ============ CONVERSATIONS ============
log("\n=== CONVERSATIONS ===")
convs = sq.execute(text("SELECT * FROM conversations ORDER BY id")).fetchall()
conv_cols = list(sq.execute(text("SELECT * FROM conversations LIMIT 1")).keys())
log(f"Total in SQLite: {len(convs)}")

# Check existing
session = get_session()
existing_convs = set(r[0] for r in session.execute(text("SELECT id FROM conversations")).fetchall())
session.close()
log(f"Already in PG: {len(existing_convs)}")

conv_done = 0
conv_skip = 0
conv_err = 0
conv_total = len(convs)

for i, row in enumerate(convs):
    data = dict(zip(conv_cols, row))
    
    if data["id"] in existing_convs:
        conv_skip += 1
        continue
    
    # Check if client exists in PG
    sq_client_id = data["client_id"]
    tg_id = sq_client_map.get(sq_client_id)
    if not tg_id or tg_id not in pg_clients:
        conv_skip += 1
        continue
    
    # Update client_id to PG client_id
    data["client_id"] = pg_clients[tg_id]
    
    # Fix booleans
    for c in ["is_deleted", "auto_reply_sent", "owner_replied"]:
        if c in data and data[c] is not None:
            data[c] = bool(data[c])
    
    try:
        session = get_session()
        c = ", ".join([f'"{k}"' for k in data.keys()])
        v = ", ".join([f":{k}" for k in data.keys()])
        session.execute(text(f'INSERT INTO conversations ({c}) VALUES ({v})'), data)
        session.commit()
        session.close()
        conv_done += 1
    except:
        conv_err += 1
    
    if (i + 1) % 10 == 0 or i == conv_total - 1:
        log(f"Conversations: {conv_done}/{conv_total} done, {conv_skip} skip, {conv_err} err")

log(f"CONVERSATIONS COMPLETE: {conv_done} done")

# ============ MESSAGES (last 10 per client) ============
log("\n=== MESSAGES (last 10 per client) ===")

# Get last 10 messages for each client that exists in PG
msg_query = """
    SELECT m.* FROM messages m
    INNER JOIN (
        SELECT client_id, id FROM (
            SELECT client_id, id, ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY sent_at DESC) as rn
            FROM messages
        ) WHERE rn <= 10
    ) sub ON m.id = sub.id
    ORDER BY m.client_id, m.sent_at DESC
"""
messages = sq.execute(text(msg_query)).fetchall()
msg_cols = list(sq.execute(text("SELECT * FROM messages LIMIT 1")).keys())
log(f"Messages to migrate (last 10 per client): {len(messages)}")

# Check existing
session = get_session()
existing_msgs = set(r[0] for r in session.execute(text("SELECT id FROM messages")).fetchall())
session.close()
log(f"Already in PG: {len(existing_msgs)}")

msg_done = 0
msg_skip = 0
msg_err = 0
msg_total = len(messages)

for i, row in enumerate(messages):
    data = dict(zip(msg_cols, row))
    
    if data["id"] in existing_msgs:
        msg_skip += 1
        continue
    
    # Check if client exists in PG
    sq_client_id = data["client_id"]
    tg_id = sq_client_map.get(sq_client_id)
    if not tg_id or tg_id not in pg_clients:
        msg_skip += 1
        continue
    
    # Update client_id
    data["client_id"] = pg_clients[tg_id]
    
    # conversation_id - set to NULL if not exists
    data["conversation_id"] = None
    
    try:
        session = get_session()
        c = ", ".join([f'"{k}"' for k in data.keys()])
        v = ", ".join([f":{k}" for k in data.keys()])
        session.execute(text(f'INSERT INTO messages ({c}) VALUES ({v})'), data)
        session.commit()
        session.close()
        msg_done += 1
    except Exception as e:
        msg_err += 1
    
    if (i + 1) % 50 == 0 or i == msg_total - 1:
        log(f"Messages: {msg_done}/{msg_total} done, {msg_skip} skip, {msg_err} err")

log(f"MESSAGES COMPLETE: {msg_done} done")

# ============ ORDERS ============
log("\n=== ORDERS ===")
orders = sq.execute(text("SELECT * FROM orders ORDER BY id")).fetchall()
order_cols = list(sq.execute(text("SELECT * FROM orders LIMIT 1")).keys())
log(f"Total in SQLite: {len(orders)}")

session = get_session()
existing_orders = set(r[0] for r in session.execute(text("SELECT id FROM orders")).fetchall())
session.close()
log(f"Already in PG: {len(existing_orders)}")

ord_done = 0
ord_skip = 0
ord_err = 0
ord_total = len(orders)

for i, row in enumerate(orders):
    data = dict(zip(order_cols, row))
    
    if data["id"] in existing_orders:
        ord_skip += 1
        continue
    
    sq_client_id = data["client_id"]
    tg_id = sq_client_map.get(sq_client_id)
    if not tg_id or tg_id not in pg_clients:
        ord_skip += 1
        continue
    
    data["client_id"] = pg_clients[tg_id]
    data["conversation_id"] = None
    
    for c in ["has_ab_test", "has_title", "has_rush"]:
        if c in data and data[c] is not None:
            data[c] = bool(data[c])
    
    try:
        session = get_session()
        c = ", ".join([f'"{k}"' for k in data.keys()])
        v = ", ".join([f":{k}" for k in data.keys()])
        session.execute(text(f'INSERT INTO orders ({c}) VALUES ({v})'), data)
        session.commit()
        session.close()
        ord_done += 1
    except:
        ord_err += 1
    
    if (i + 1) % 5 == 0 or i == ord_total - 1:
        log(f"Orders: {ord_done}/{ord_total} done, {ord_skip} skip, {ord_err} err")

log(f"ORDERS COMPLETE: {ord_done} done")

# ============ REMINDERS ============
log("\n=== REMINDERS ===")
reminders = sq.execute(text("SELECT * FROM reminders ORDER BY id")).fetchall()
if reminders:
    rem_cols = list(sq.execute(text("SELECT * FROM reminders LIMIT 1")).keys())
    log(f"Total in SQLite: {len(reminders)}")
    
    session = get_session()
    existing_rems = set(r[0] for r in session.execute(text("SELECT id FROM reminders")).fetchall())
    session.close()
    
    rem_done = 0
    rem_skip = 0
    
    for row in reminders:
        data = dict(zip(rem_cols, row))
        if data["id"] in existing_rems:
            rem_skip += 1
            continue
        
        sq_client_id = data["client_id"]
        tg_id = sq_client_map.get(sq_client_id)
        if not tg_id or tg_id not in pg_clients:
            rem_skip += 1
            continue
        
        data["client_id"] = pg_clients[tg_id]
        data["conversation_id"] = None
        
        for c in ["is_sent", "is_completed"]:
            if c in data and data[c] is not None:
                data[c] = bool(data[c])
        
        try:
            session = get_session()
            c = ", ".join([f'"{k}"' for k in data.keys()])
            v = ", ".join([f":{k}" for k in data.keys()])
            session.execute(text(f'INSERT INTO reminders ({c}) VALUES ({v})'), data)
            session.commit()
            session.close()
            rem_done += 1
        except:
            pass
    
    log(f"REMINDERS COMPLETE: {rem_done} done, {rem_skip} skip")
else:
    log("No reminders")

# Reset sequences
log("\n=== Resetting sequences ===")
for t in ["conversations", "messages", "orders", "reminders"]:
    try:
        session = get_session()
        m = session.execute(text(f"SELECT MAX(id) FROM {t}")).scalar()
        if m:
            session.execute(text(f"SELECT setval('{t}_id_seq', {m})"))
            session.commit()
        session.close()
    except:
        pass

sq.close()
log("\n=== ALL DONE! ===")
