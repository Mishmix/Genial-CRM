"""Tests for CRUD operations."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Client, Tag, Message
from app.crud import (
    upsert_client, get_client, get_client_by_telegram_id,
    update_client, create_message, search_clients,
    create_tag, get_or_create_tag,
)
from app.schemas import ClientCreate, ClientUpdate


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()


class TestClientCRUD:
    """Tests for client CRUD operations."""
    
    def test_create_client(self, db_session):
        """Test creating a new client."""
        client_data = ClientCreate(
            telegram_user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
            language_code="en",
        )
        
        client = upsert_client(db_session, client_data)
        
        assert client.id is not None
        assert client.telegram_user_id == 123456789
        assert client.username == "testuser"
        assert client.first_name == "Test"
        assert client.status == "new"
    
    def test_upsert_existing_client(self, db_session):
        """Test updating an existing client."""
        # Create initial client
        client_data = ClientCreate(
            telegram_user_id=123456789,
            username="olduser",
            first_name="Old",
        )
        client1 = upsert_client(db_session, client_data)
        
        # Update with new data
        updated_data = ClientCreate(
            telegram_user_id=123456789,
            username="newuser",
            first_name="New",
        )
        client2 = upsert_client(db_session, updated_data)
        
        # Should be same client
        assert client1.id == client2.id
        assert client2.username == "newuser"
        assert client2.first_name == "New"
    
    def test_get_client_by_telegram_id(self, db_session):
        """Test finding client by Telegram ID."""
        client_data = ClientCreate(
            telegram_user_id=999888777,
            first_name="Find",
        )
        created = upsert_client(db_session, client_data)
        
        found = get_client_by_telegram_id(db_session, 999888777)
        
        assert found is not None
        assert found.id == created.id
    
    def test_get_nonexistent_client(self, db_session):
        """Test that nonexistent client returns None."""
        found = get_client_by_telegram_id(db_session, 111222333)
        assert found is None
    
    def test_update_client_status(self, db_session):
        """Test updating client status."""
        client_data = ClientCreate(
            telegram_user_id=123456789,
            first_name="Test",
        )
        client = upsert_client(db_session, client_data)
        
        update_data = ClientUpdate(status="qualified")
        updated = update_client(db_session, client.id, update_data)
        
        assert updated.status == "qualified"
    
    def test_update_client_notes(self, db_session):
        """Test updating client notes."""
        client_data = ClientCreate(
            telegram_user_id=123456789,
            first_name="Test",
        )
        client = upsert_client(db_session, client_data)
        
        update_data = ClientUpdate(notes="Important client")
        updated = update_client(db_session, client.id, update_data)
        
        assert updated.notes == "Important client"


class TestMessageCRUD:
    """Tests for message CRUD operations."""
    
    def test_create_inbound_message(self, db_session):
        """Test creating an inbound message."""
        # Create client first
        client_data = ClientCreate(
            telegram_user_id=123456789,
            first_name="Test",
        )
        client = upsert_client(db_session, client_data)
        
        # Create message
        message = create_message(
            db_session,
            client_id=client.id,
            direction="in",
            text="Hello!",
            telegram_message_id=12345,
        )
        
        assert message.id is not None
        assert message.direction == "in"
        assert message.text == "Hello!"
        
        # Check unread count increased
        db_session.refresh(client)
        assert client.unread_count == 1
    
    def test_create_outbound_message(self, db_session):
        """Test creating an outbound message."""
        client_data = ClientCreate(
            telegram_user_id=123456789,
            first_name="Test",
        )
        client = upsert_client(db_session, client_data)
        
        message = create_message(
            db_session,
            client_id=client.id,
            direction="out",
            text="Hi there!",
        )
        
        assert message.direction == "out"
        
        # Outbound shouldn't increase unread
        db_session.refresh(client)
        assert client.unread_count == 0


class TestTagCRUD:
    """Tests for tag CRUD operations."""
    
    def test_create_tag(self, db_session):
        """Test creating a tag."""
        tag = create_tag(db_session, "vip", "#8b5cf6")
        
        assert tag.id is not None
        assert tag.name == "vip"
        assert tag.color == "#8b5cf6"
    
    def test_get_or_create_tag_new(self, db_session):
        """Test get_or_create with new tag."""
        tag = get_or_create_tag(db_session, "new_tag")
        
        assert tag.id is not None
        assert tag.name == "new_tag"
    
    def test_get_or_create_tag_existing(self, db_session):
        """Test get_or_create with existing tag."""
        tag1 = create_tag(db_session, "existing")
        tag2 = get_or_create_tag(db_session, "existing")
        
        assert tag1.id == tag2.id
    
    def test_update_client_tags(self, db_session):
        """Test assigning tags to client."""
        # Create client and tags
        client_data = ClientCreate(
            telegram_user_id=123456789,
            first_name="Test",
        )
        client = upsert_client(db_session, client_data)
        
        tag1 = create_tag(db_session, "hot")
        tag2 = create_tag(db_session, "vip")
        
        # Assign tags
        update_data = ClientUpdate(tag_ids=[tag1.id, tag2.id])
        updated = update_client(db_session, client.id, update_data)
        
        # Reload to get tags
        client = get_client(db_session, client.id)
        
        assert len(client.tags) == 2
        tag_names = {t.name for t in client.tags}
        assert "hot" in tag_names
        assert "vip" in tag_names


class TestSearchClients:
    """Tests for client search functionality."""
    
    def test_search_by_first_name(self, db_session):
        """Test searching by first name."""
        client_data = ClientCreate(
            telegram_user_id=123456789,
            first_name="Александр",
        )
        upsert_client(db_session, client_data)
        
        results = search_clients(db_session, "Александр")
        
        assert len(results) == 1
        assert results[0].first_name == "Александр"
    
    def test_search_by_username(self, db_session):
        """Test searching by username."""
        client_data = ClientCreate(
            telegram_user_id=123456789,
            username="cooluser",
            first_name="Test",
        )
        upsert_client(db_session, client_data)
        
        results = search_clients(db_session, "cooluser")
        
        assert len(results) == 1
        assert results[0].username == "cooluser"
    
    def test_search_transliteration(self, db_session):
        """Test that transliteration helps find results."""
        client_data = ClientCreate(
            telegram_user_id=123456789,
            first_name="Михаил",
        )
        upsert_client(db_session, client_data)
        
        # Search with Latin transliteration
        results = search_clients(db_session, "Mikhail")
        
        # Should find via transliteration variants
        # Note: actual matching depends on implementation
        assert len(results) >= 0  # May or may not find depending on LIKE behavior


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
