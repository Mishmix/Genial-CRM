"""SQLAlchemy models for CRM."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table, Index, Float, BigInteger, JSON, func
from sqlalchemy.orm import relationship
from app.db import Base

client_tags = Table(
    "client_tags", Base.metadata,
    Column("client_id", Integer, ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), nullable=True)
    avatar_file_id = Column(String(255), nullable=True)
    avatar_local_path = Column(String(512), nullable=True)
    business_connection_id = Column(String(255), nullable=True)
    status = Column(String(50), default="new", nullable=False)
    notes = Column(Text, nullable=True)
    sticky_note = Column(Text, nullable=True)
    source = Column(String(100), default="telegram")
    external_contact = Column(String(255), nullable=True)
    search_index = Column(Text, nullable=True)
    buffer_messages = Column(Text, nullable=True)
    thumbnail_processed = Column(Boolean, default=False)
    owner_replied = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime, nullable=True)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    merged_from = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)
    last_auto_reply_at = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_client_message_at = Column(DateTime, nullable=True)
    unread_count = Column(Integer, default=0)
    tags = relationship("Tag", secondary=client_tags, back_populates="clients")
    messages = relationship("Message", back_populates="client", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="client", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="client", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="client", cascade="all, delete-orphan")
    aliases = relationship("ClientAlias", back_populates="client", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_clients_status", "status"), Index("ix_clients_last_message", "last_message_at"), Index("ix_clients_archived", "is_archived"),)


class ClientAlias(Base):
    __tablename__ = "client_aliases"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    telegram_id = Column(BigInteger, nullable=True)
    username = Column(String(255), nullable=True)
    client = relationship("Client", back_populates="aliases")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    business_connection_id = Column(String(255), nullable=True)
    source = Column(String(50), default="telegram")
    category = Column(String(50), nullable=True)
    status = Column(String(50), default="new", nullable=False)
    rejection_reason = Column(String(50), nullable=True)
    rejection_custom = Column(Text, nullable=True)
    rejection_normalized_category = Column(String(50), nullable=True, index=True)
    rejection_classification_confidence = Column(Float, nullable=True)
    rejection_classified_at = Column(DateTime, nullable=True)
    reactivation_attempts = Column(Integer, nullable=True)
    last_reactivation_at = Column(DateTime, nullable=True)
    messages_json = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deletion_reason = Column(Text, nullable=True)
    auto_reply_sent = Column(Boolean, default=False)
    owner_replied = Column(Boolean, default=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    owner_replied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    unread_count = Column(Integer, default=0)
    client = relationship("Client", back_populates="conversations")
    orders = relationship("Order", back_populates="conversation")
    reminders = relationship("Reminder", back_populates="conversation")
    __table_args__ = (Index("ix_conversations_client", "client_id"), Index("ix_conversations_status", "status"), Index("ix_conversations_created", "created_at"),)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    direction = Column(String(10), nullable=False)
    text = Column(Text, nullable=True)
    message_type = Column(String(20), default="text")
    telegram_message_id = Column(Integer, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    transcription = Column(Text, nullable=True)
    transcription_status = Column(String(20), nullable=True)  # pending|done|failed
    client = relationship("Client", back_populates="messages")
    __table_args__ = (Index("ix_messages_client_sent", "client_id", "sent_at"),)

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(20), default="#3b82f6")
    clients = relationship("Client", secondary=client_tags, back_populates="tags")

class Template(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    language = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    is_auto_reply = Column(Boolean, default=False)
    category = Column(String(50), nullable=True)  # "thumbnail", "email_lead", "other"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("ix_templates_lang_active", "language", "is_active"),)

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    role = Column(String(50), default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    auth_type = Column(String(50), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    service_type = Column(String(50), nullable=False)
    quantity = Column(Integer, default=1)
    amount = Column(Float, nullable=True)
    currency = Column(String(10), default="USD")
    has_ab_test = Column(Boolean, default=False)
    has_title = Column(Boolean, default=False)
    has_rush = Column(Boolean, default=False)
    deadline_type = Column(String(20), nullable=True)
    deadline_date = Column(DateTime, nullable=True)
    deadline_range = Column(String(50), nullable=True)
    deadline_custom = Column(String(255), nullable=True)
    deadline_calculated = Column(DateTime, nullable=True)
    status = Column(String(50), default="pending")
    notes = Column(Text, nullable=True)
    source = Column(String(20), default="manual")
    ai_confidence = Column(Float, nullable=True)
    todoist_task_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    client = relationship("Client", back_populates="orders")
    conversation = relationship("Conversation", back_populates="orders")
    __table_args__ = (Index("ix_orders_client", "client_id"), Index("ix_orders_conversation", "conversation_id"), Index("ix_orders_status", "status"), Index("ix_orders_deadline", "deadline_date"),)

class RejectionReason(Base):
    __tablename__ = "rejection_reasons"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    label = Column(String(255), nullable=False)
    emoji = Column(String(10), nullable=True)
    sort_order = Column(Integer, default=0)

class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    reminder_type = Column(String(50), nullable=False)
    text = Column(Text, nullable=False)
    remind_at = Column(DateTime, nullable=False)
    is_sent = Column(Boolean, default=False)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    client = relationship("Client", back_populates="reminders")
    conversation = relationship("Conversation", back_populates="reminders")
    __table_args__ = (Index("ix_reminders_remind_at", "remind_at"), Index("ix_reminders_completed", "is_completed"),)

class Digest(Base):
    __tablename__ = "digests"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), nullable=False, index=True)  # morning|evening
    content = Column(Text, nullable=False)
    raw_response = Column(JSON, nullable=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    delivery_message_id = Column(Integer, nullable=True)
    routine_session_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    __table_args__ = (Index("ix_digests_created_at", "created_at"),)


class ClientEnrichment(Base):
    __tablename__ = "client_enrichments"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    niche = Column(String(50), nullable=True)
    channel_name = Column(String(255), nullable=True)
    channel_size_bucket = Column(String(20), nullable=True)
    temperature = Column(String(20), nullable=True)
    communication_style = Column(String(30), nullable=True)
    price_sensitivity = Column(String(20), nullable=True)
    decision_speed = Column(String(20), nullable=True)
    last_summary = Column(Text, nullable=True)
    pain_points = Column(JSON, nullable=True)
    value_drivers = Column(JSON, nullable=True)
    next_best_action = Column(Text, nullable=True)
    ai_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=datetime.utcnow, nullable=False)


class TodoistSyncLog(Base):
    __tablename__ = "todoist_sync_logs"
    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    summary_md = Column(Text, nullable=True)
    applied_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    actions_json = Column(JSON, nullable=True)
    routine_session_url = Column(String(512), nullable=True)
    telegram_message_id = Column(Integer, nullable=True)


class DailyStats(Base):
    __tablename__ = "daily_stats"
    date = Column(String(10), primary_key=True)
    new_conversations = Column(Integer, default=0)
    thumbnail_leads = Column(Integer, default=0)
    other_leads = Column(Integer, default=0)
    orders_count = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
