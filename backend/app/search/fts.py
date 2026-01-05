"""Full-text search with SQLite FTS5."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.search.normalize import build_client_search_text


def init_fts_table(db: Session):
    """Initialize FTS5 virtual table for client search."""
    db.execute(text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS clients_fts USING fts5(
            client_id,
            display_name,
            username,
            search_variants,
            content='',
            tokenize='unicode61'
        )
    """))
    db.commit()


def update_client_fts(
    db: Session,
    client_id: int,
    first_name: str,
    last_name: str = None,
    username: str = None,
):
    """Update FTS index for a client."""
    # Delete existing entry
    db.execute(
        text("DELETE FROM clients_fts WHERE client_id = :client_id"),
        {"client_id": str(client_id)}
    )
    
    # Build search text
    display_name = f"{first_name} {last_name or ''}".strip()
    search_variants = build_client_search_text(first_name, last_name, username)
    
    # Insert new entry
    db.execute(
        text("""
            INSERT INTO clients_fts (client_id, display_name, username, search_variants)
            VALUES (:client_id, :display_name, :username, :search_variants)
        """),
        {
            "client_id": str(client_id),
            "display_name": display_name,
            "username": username or "",
            "search_variants": search_variants,
        }
    )
    db.commit()


def search_clients_fts(db: Session, query: str, limit: int = 50) -> list:
    """Search clients using FTS5."""
    from app.search.normalize import generate_search_variants
    
    variants = generate_search_variants(query)
    
    # Build FTS query with OR
    fts_terms = []
    for variant in variants:
        # Escape special FTS characters
        escaped = variant.replace('"', '""')
        fts_terms.append(f'"{escaped}"*')
    
    if not fts_terms:
        return []
    
    fts_query = " OR ".join(fts_terms)
    
    result = db.execute(
        text("""
            SELECT client_id FROM clients_fts
            WHERE clients_fts MATCH :query
            LIMIT :limit
        """),
        {"query": fts_query, "limit": limit}
    )
    
    return [int(row[0]) for row in result.fetchall()]
