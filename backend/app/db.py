"""Database connection and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

# Determine database type
is_sqlite = settings.database_url.startswith("sqlite")

# Configure engine based on database type
if is_sqlite:
    # SQLite specific configuration
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.env == "development",
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL configuration — tuned for single-user CRM with low concurrency.
    # pool_size=2, max_overflow=3 → up to 5 connections (vs default 5+10=15),
    # which trims ~25 MB of idle Postgres client buffers without affecting throughput.
    # pool_recycle=1800 drops idle connections after 30 min to prevent state accumulation.
    engine = create_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=3,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=settings.env == "development",
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
