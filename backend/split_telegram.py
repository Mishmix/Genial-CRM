"""Split large Telegram export into smaller chunks."""
import json
import sys
import os

def split_export(input_file: str, chats_per_file: int = 50):
    """Split Telegram export into smaller files."""
    print(f"Reading {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chats = data.get("chats", {}).get("list", [])
    if not chats:
        print("No chats found!")
        return
    
    print(f"Found {len(chats)} chats")
    
    # Split into chunks
    chunks = [chats[i:i + chats_per_file] for i in range(0, len(chats), chats_per_file)]
    
    base_name = os.path.splitext(input_file)[0]
    
    for idx, chunk in enumerate(chunks):
        output_file = f"{base_name}_part{idx + 1}.json"
        output_data = {
            "chats": {
                "list": chunk
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False)
        
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"Created {output_file} ({len(chunk)} chats, {size_mb:.1f} MB)")
    
    print(f"\nDone! Created {len(chunks)} files")
    print("Upload each file one by one through the import interface")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_telegram.py result.json [chats_per_file]")
        print("Example: python split_telegram.py result.json 30")
        sys.exit(1)
    
    input_file = sys.argv[1]
    chats_per_file = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    
    split_export(input_file, chats_per_file)
