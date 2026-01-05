"""Migrate data from SQLite to PostgreSQL with proper BIGINT columns."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

def migrate():
    print("Connecting...")
    sqlite_engine = create_engine(SQLITE_URL)
    sqlite_conn = sqlite_engine.connect()
    
    pg_engine = create_engine(POSTGRES_URL)
    pg_conn = pg_engine.connect()
    
    # Drop ALL tables
    print("Dropping all tables...")
    pg_conn.execute(text("DROP SCHEMA public CASCADE"))
    pg_conn.execute(text("CREATE SCHEMA public"))
    pg_conn.commit()
    
    # Create tables with BIGINT using raw SQL
    print("Creating tables with BIGINT...")
    
    # Create all tables with proper types
    create_sql = """
    CREATE TABLE settings (
        key VARCHAR(100) PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE admins (
        id SERIAL PRIMARY KEY,
        telegram_user_id BIGINT UNIQUE NOT NULL,
        username VARCHAR(255),
        role VARCHAR(50) DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE tags (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL,
        color VARCHAR(20) DEFAULT '#3b82f6'
    );
    
    CREATE TABLE templates (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        language VARCHAR(10) NOT NULL,
        content TEXT NOT NULL,
        is_auto_reply BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX ix_templates_lang_active ON templates(language, is_active);
    
    CREATE TABLE rejection_reasons (
        id SERIAL PRIMARY KEY,
        code VARCHAR(50) UNIQUE NOT NULL,
        label VARCHAR(255) NOT NULL,
        emoji VARCHAR(10),
        sort_order INTEGER DEFAULT 0
    );
    
    CREATE TABLE clients (
        id SERIAL PRIMARY KEY,
        telegram_user_id BIGINT UNIQUE NOT NULL,
        username VARCHAR(255),
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255),
        language_code VARCHAR(10),
        avatar_file_id VARCHAR(255),
        avatar_local_path VARCHAR(512),
        business_connection_id VARCHAR(255),
        status VARCHAR(50) DEFAULT 'new' NOT NULL,
        notes TEXT,
        sticky_note TEXT,
        source VARCHAR(100) DEFAULT 'telegram',
        external_contact VARCHAR(255),
        search_index TEXT,
        buffer_messages TEXT,
        thumbnail_processed BOOLEAN DEFAULT FALSE,
        owner_replied BOOLEAN DEFAULT FALSE,
        is_archived BOOLEAN DEFAULT FALSE,
        archived_at TIMESTAMP,
        total_orders INTEGER DEFAULT 0,
        total_spent FLOAT DEFAULT 0.0,
        merged_from TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_message_at TIMESTAMP,
        last_auto_reply_at TIMESTAMP,
        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_client_message_at TIMESTAMP,
        unread_count INTEGER DEFAULT 0
    );
    CREATE INDEX ix_clients_telegram_user_id ON clients(telegram_user_id);
    CREATE INDEX ix_clients_username ON clients(username);
    CREATE INDEX ix_clients_status ON clients(status);
    CREATE INDEX ix_clients_last_message ON clients(last_message_at);
    CREATE INDEX ix_clients_archived ON clients(is_archived);
    
    CREATE TABLE client_aliases (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        telegram_id BIGINT,
        username VARCHAR(255)
    );
    
    CREATE TABLE client_tags (
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (client_id, tag_id)
    );
    
    CREATE TABLE conversations (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        business_connection_id VARCHAR(255),
        source VARCHAR(50) DEFAULT 'telegram',
        category VARCHAR(50),
        status VARCHAR(50) DEFAULT 'new' NOT NULL,
        rejection_reason VARCHAR(50),
        rejection_custom TEXT,
        messages_json TEXT,
        is_deleted BOOLEAN DEFAULT FALSE,
        deletion_reason TEXT,
        auto_reply_sent BOOLEAN DEFAULT FALSE,
        owner_replied BOOLEAN DEFAULT FALSE,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        owner_replied_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        unread_count INTEGER DEFAULT 0
    );
    CREATE INDEX ix_conversations_client ON conversations(client_id);
    CREATE INDEX ix_conversations_status ON conversations(status);
    CREATE INDEX ix_conversations_created ON conversations(created_at);
    
    CREATE TABLE messages (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
        direction VARCHAR(10) NOT NULL,
        text TEXT,
        message_type VARCHAR(20) DEFAULT 'text',
        telegram_message_id BIGINT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
    );
    CREATE INDEX ix_messages_client_sent ON messages(client_id, sent_at);
    
    CREATE TABLE orders (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
        service_type VARCHAR(50) NOT NULL,
        quantity INTEGER DEFAULT 1,
        amount FLOAT,
        currency VARCHAR(10) DEFAULT 'USD',
        has_ab_test BOOLEAN DEFAULT FALSE,
        has_title BOOLEAN DEFAULT FALSE,
        has_rush BOOLEAN DEFAULT FALSE,
        deadline_type VARCHAR(20),
        deadline_date TIMESTAMP,
        deadline_range VARCHAR(50),
        deadline_custom VARCHAR(255),
        deadline_calculated TIMESTAMP,
        status VARCHAR(50) DEFAULT 'pending',
        notes TEXT,
        source VARCHAR(20) DEFAULT 'manual',
        ai_confidence FLOAT,
        todoist_task_id VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );
    CREATE INDEX ix_orders_client ON orders(client_id);
    CREATE INDEX ix_orders_conversation ON orders(conversation_id);
    CREATE INDEX ix_orders_status ON orders(status);
    CREATE INDEX ix_orders_deadline ON orders(deadline_date);
    
    CREATE TABLE reminders (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
        conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
        reminder_type VARCHAR(50) NOT NULL,
        text TEXT NOT NULL,
        remind_at TIMESTAMP NOT NULL,
        is_sent BOOLEAN DEFAULT FALSE,
        is_completed BOOLEAN DEFAULT FALSE,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX ix_reminders_remind_at ON reminders(remind_at);
    CREATE INDEX ix_reminders_completed ON reminders(is_completed);
    
    CREATE TABLE sessions (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(255) UNIQUE NOT NULL,
        admin_id INTEGER REFERENCES admins(id) ON DELETE CASCADE,
        telegram_user_id BIGINT,
        auth_type VARCHAR(50) NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX ix_sessions_session_id ON sessions(session_id);
    
    CREATE TABLE daily_stats (
        date VARCHAR(10) PRIMARY KEY,
        new_conversations INTEGER DEFAULT 0,
        thumbnail_leads INTEGER DEFAULT 0,
        other_leads INTEGER DEFAULT 0,
        orders_count INTEGER DEFAULT 0,
        revenue FLOAT DEFAULT 0.0
    );
    """
    
    for stmt in create_sql.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                pg_conn.execute(text(stmt))
            except Exception as e:
                print(f"  SQL error: {str(e)[:80]}")
    pg_conn.commit()
    print("Tables created!")
    
    # Migrate data
    for table_name in TABLES:
        try:
            result = sqlite_conn.execute(text(f"SELECT * FROM {table_name}"))
            rows = result.fetchall()
            columns = list(result.keys())
            
            if not rows:
                print(f"  {table_name}: empty")
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
            print(f"  {table_name}: {count}/{len(rows)}{err_str}")
            
        except Exception as e:
            print(f"  {table_name}: ERROR - {str(e)[:60]}")
            pg_conn.rollback()
    
    # Reset sequences
    print("Resetting sequences...")
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
    
    print("\nDone!")
    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    migrate()
