"""Final migration - create tables and migrate data."""
import sys
from sqlalchemy import create_engine, text

SQLITE_URL = "sqlite:///crm.db"
POSTGRES_URL = "postgresql://postgres:AJTHvKxErblWKUfANfeCPXpBSoOOxMBF@switchyard.proxy.rlwy.net:44751/railway"

print("Connecting...", flush=True)
sqlite_engine = create_engine(SQLITE_URL)
sqlite_conn = sqlite_engine.connect()

pg_engine = create_engine(POSTGRES_URL)
pg_conn = pg_engine.connect()

# Drop tables one by one (faster than DROP SCHEMA)
print("Dropping tables...", flush=True)
for t in ["sessions", "reminders", "orders", "messages", "client_aliases", 
          "client_tags", "conversations", "clients", "daily_stats",
          "rejection_reasons", "templates", "tags", "admins", "settings"]:
    try:
        pg_conn.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE"))
        pg_conn.commit()
    except:
        pg_conn.rollback()

# Create tables
print("Creating tables...", flush=True)
create_sql = """
CREATE TABLE IF NOT EXISTS settings (key VARCHAR(100) PRIMARY KEY, value TEXT, updated_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS admins (id SERIAL PRIMARY KEY, telegram_user_id BIGINT UNIQUE NOT NULL, username VARCHAR(255), role VARCHAR(50), created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS tags (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL, color VARCHAR(20));
CREATE TABLE IF NOT EXISTS templates (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, language VARCHAR(10) NOT NULL, content TEXT NOT NULL, is_auto_reply BOOLEAN, is_active BOOLEAN, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS rejection_reasons (id SERIAL PRIMARY KEY, code VARCHAR(50) UNIQUE NOT NULL, label VARCHAR(255) NOT NULL, emoji VARCHAR(10), sort_order INTEGER);
CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, telegram_user_id BIGINT UNIQUE NOT NULL, username VARCHAR(255), first_name VARCHAR(255) NOT NULL, last_name VARCHAR(255), language_code VARCHAR(10), avatar_file_id VARCHAR(255), avatar_local_path VARCHAR(512), business_connection_id VARCHAR(255), status VARCHAR(50), notes TEXT, sticky_note TEXT, source VARCHAR(100), external_contact VARCHAR(255), search_index TEXT, buffer_messages TEXT, thumbnail_processed BOOLEAN, owner_replied BOOLEAN, is_archived BOOLEAN, archived_at TIMESTAMP, total_orders INTEGER, total_spent FLOAT, merged_from TEXT, created_at TIMESTAMP, updated_at TIMESTAMP, last_message_at TIMESTAMP, last_auto_reply_at TIMESTAMP, first_seen_at TIMESTAMP, last_client_message_at TIMESTAMP, unread_count INTEGER);
CREATE TABLE IF NOT EXISTS client_aliases (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, telegram_id BIGINT, username VARCHAR(255));
CREATE TABLE IF NOT EXISTS client_tags (client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE, PRIMARY KEY (client_id, tag_id));
CREATE TABLE IF NOT EXISTS conversations (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, business_connection_id VARCHAR(255), source VARCHAR(50), category VARCHAR(50), status VARCHAR(50), rejection_reason VARCHAR(50), rejection_custom TEXT, messages_json TEXT, is_deleted BOOLEAN, deletion_reason TEXT, auto_reply_sent BOOLEAN, owner_replied BOOLEAN, started_at TIMESTAMP, owner_replied_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP, unread_count INTEGER);
CREATE TABLE IF NOT EXISTS messages (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL, direction VARCHAR(10) NOT NULL, text TEXT, message_type VARCHAR(20), telegram_message_id BIGINT, sent_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL, service_type VARCHAR(50) NOT NULL, quantity INTEGER, amount FLOAT, currency VARCHAR(10), has_ab_test BOOLEAN, has_title BOOLEAN, has_rush BOOLEAN, deadline_type VARCHAR(20), deadline_date TIMESTAMP, deadline_range VARCHAR(50), deadline_custom VARCHAR(255), deadline_calculated TIMESTAMP, status VARCHAR(50), notes TEXT, source VARCHAR(20), ai_confidence FLOAT, todoist_task_id VARCHAR(100), created_at TIMESTAMP, completed_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS reminders (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL, reminder_type VARCHAR(50) NOT NULL, text TEXT NOT NULL, remind_at TIMESTAMP NOT NULL, is_sent BOOLEAN, is_completed BOOLEAN, completed_at TIMESTAMP, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS sessions (id SERIAL PRIMARY KEY, session_id VARCHAR(255) UNIQUE NOT NULL, admin_id INTEGER REFERENCES admins(id) ON DELETE CASCADE, telegram_user_id BIGINT, auth_type VARCHAR(50) NOT NULL, expires_at TIMESTAMP NOT NULL, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS daily_stats (date VARCHAR(10) PRIMARY KEY, new_conversations INTEGER, thumbnail_leads INTEGER, other_leads INTEGER, orders_count INTEGER, revenue FLOAT);
"""
for stmt in create_sql.strip().split(';'):
    if stmt.strip():
        try:
            pg_conn.execute(text(stmt))
            pg_conn.commit()
        except Exception as e:
            print(f"  SQL error: {str(e)[:50]}", flush=True)
            pg_conn.rollback()

print("Tables created!", flush=True)

# Migrate data
TABLES = ["settings", "admins", "tags", "templates", "rejection_reasons", "clients", "client_aliases", "client_tags", "conversations", "messages", "orders", "reminders", "sessions", "daily_stats"]
BOOLEAN_COLS = {"templates": ["is_auto_reply", "is_active"], "clients": ["thumbnail_processed", "owner_replied", "is_archived"], "orders": ["has_ab_test", "has_title", "has_rush"], "conversations": ["is_deleted", "auto_reply_sent", "owner_replied"], "reminders": ["is_sent", "is_completed"]}

for table_name in TABLES:
    try:
        result = sqlite_conn.execute(text(f"SELECT * FROM {table_name}"))
        rows = result.fetchall()
        columns = list(result.keys())
        if not rows:
            print(f"  {table_name}: empty", flush=True)
            continue
        count = 0
        for row in rows:
            data = dict(zip(columns, row))
            if table_name in BOOLEAN_COLS:
                for col in BOOLEAN_COLS[table_name]:
                    if col in data and data[col] is not None:
                        data[col] = bool(data[col])
            cols = ", ".join([f'"{k}"' for k in data.keys()])
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            try:
                pg_conn.execute(text(f'INSERT INTO {table_name} ({cols}) VALUES ({placeholders})'), data)
                count += 1
            except:
                pg_conn.rollback()
        pg_conn.commit()
        print(f"  {table_name}: {count}/{len(rows)}", flush=True)
    except Exception as e:
        print(f"  {table_name}: ERROR", flush=True)
        pg_conn.rollback()

# Reset sequences
print("Sequences...", flush=True)
for t in ["admins", "tags", "templates", "rejection_reasons", "clients", "client_aliases", "conversations", "messages", "orders", "reminders", "sessions"]:
    try:
        r = pg_conn.execute(text(f"SELECT MAX(id) FROM {t}"))
        m = r.scalar()
        if m:
            pg_conn.execute(text(f"SELECT setval('{t}_id_seq', {m})"))
            pg_conn.commit()
    except:
        pass

print("DONE!", flush=True)
