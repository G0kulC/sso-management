"""
database.py - Database connection and session management
Handles SQLAlchemy engine creation and session lifecycle
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create the SQLAlchemy engine using the DATABASE_URL from settings
# pool_pre_ping=True ensures stale connections are detected and recycled
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# SessionLocal is the database session factory
# autocommit=False: transactions must be committed manually
# autoflush=False: objects are not auto-flushed to DB before queries
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all SQLAlchemy ORM models
Base = declarative_base()


def get_db():
    """
    Dependency generator for FastAPI routes.
    Yields a database session and ensures it is closed after use.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
