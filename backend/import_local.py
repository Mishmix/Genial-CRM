"""Import Telegram export directly to PostgreSQL."""
import json
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# PostgreSQL Railway
POSTGRES_URL = "postgresql://postgres:AJTHvKxErblWKUfANfeCPXpBSoOOxMBF@switchyard.proxy.rlwy.net:44751/railway"

# Your Telegram ID
YOUR_USER_ID = 1470411356

def parse_date(date_str):
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except:
            return None

def extract_text(msg):
    text = msg.get("text", "")
    if isinstance(text, str):
        return text if text else None
    elif isinstance(text, list):
        result = []
        for item in text:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get("text", ""))
        return "".join(result) if result else None
    return None

def import_file(file_path, engine):
    from app.models import Client, Message, Base
    
    # Create tables if not exist
    Base.metadata.create_all(bind=engine)
    
    Session = sessionmaker(bind=engine)
    db = Session()
    
    print(f"Reading {file_path}...", flush=True)
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chats = data.get("chats", {}).get("list", [])
    if not chats:
        print("No chats found!")
        return
    
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    imported_clients = 0
    imported_messages = 0
    
    for idx, chat in enumerate(chats):
        try:
            chat_type = chat.get("type", "")
            if chat_type in ["private_group", "public_group", "public_supergroup", "private_channel", "public_channel"]:
                continue
            if chat.get("name") == "Saved Messages":
                continue
            
            chat_name = chat.get("name", "Unknown")
            user_id = chat.get("id")
            if not user_id or user_id == YOUR_USER_ID:
                continue
            
            messages = chat.get("messages", [])
            if not messages:
                continue
            
            # Find or create client
            client = db.query(Client).filter(Client.telegram_user_id == user_id).first()
            
            if not client:
                name_parts = chat_name.split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else None
                
                earliest_date = None
                for msg in messages:
                    msg_date = parse_date(msg.get("date", ""))
                    if msg_date and (earliest_date is None or msg_date < earliest_date):
                        earliest_date = msg_date
                
                client = Client(
                    telegram_user_id=user_id,
                    first_name=first_name,
                    last_name=last_name,
                    status="new",
                    source="telegram-import",
                    first_seen_at=earliest_date or datetime.utcnow(),
                    created_at=datetime.utcnow(),
                )
                db.add(client)
                db.flush()
                imported_clients += 1
            
            # Get existing message IDs
            existing_ids = set(
                m[0] for m in db.query(Message.telegram_message_id)
                .filter(Message.client_id == client.id, Message.telegram_message_id.isnot(None))
                .all()
            )
            
            # Import messages
            new_messages = []
            for msg in messages:
                msg_id = msg.get("id")
                if msg_id and msg_id in existing_ids:
                    continue
                if msg.get("type", "message") != "message":
                    continue
                
                text = extract_text(msg)
                if not text:
                    continue
                
                msg_date = parse_date(msg.get("date", ""))
                if not msg_date or msg_date < one_year_ago:
                    continue
                
                from_id = msg.get("from_id") or msg.get("actor_id")
                sender_id = None
                if isinstance(from_id, str) and from_id.startswith("user"):
                    try:
                        sender_id = int(from_id[4:])
                    except:
                        pass
                elif isinstance(from_id, int):
                    sender_id = from_id
                
                direction = "out" if sender_id == YOUR_USER_ID else "in"
                
                new_messages.append(Message(
                    client_id=client.id,
                    direction=direction,
                    text=text[:10000],
                    message_type="text",
                    telegram_message_id=msg_id,
                    sent_at=msg_date,
                ))
            
            if new_messages:
                db.bulk_save_objects(new_messages)
                imported_messages += len(new_messages)
            
            # Update last_message_at
            latest = db.query(func.max(Message.sent_at)).filter(Message.client_id == client.id).scalar()
            if latest:
                client.last_message_at = latest
            
            if (idx + 1) % 10 == 0:
                db.commit()
                print(f"  Progress: {idx + 1}/{len(chats)} chats", flush=True)
                
        except Exception as e:
            print(f"  Error in chat {chat.get('name', '?')}: {e}", flush=True)
            db.rollback()
            continue
    
    db.commit()
    db.close()
    
    print(f"Done! Imported {imported_clients} clients, {imported_messages} messages", flush=True)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_local.py <file.json>")
        print("Example: python import_local.py ../../TG/result_part1.json")
        sys.exit(1)
    
    print("Connecting to PostgreSQL...", flush=True)
    engine = create_engine(POSTGRES_URL)
    
    for file_path in sys.argv[1:]:
        import_file(file_path, engine)
