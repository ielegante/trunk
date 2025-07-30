"""Database connection and session management for SQLite."""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from app.config import settings
from app.models import Base
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)


# SQLite optimizations
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance."""
    cursor = dbapi_connection.cursor()
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys=ON")
    # Use WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    # Set cache size to 64MB
    cursor.execute("PRAGMA cache_size=16000")
    # Enable automatic indexing
    cursor.execute("PRAGMA automatic_index=ON")
    # Set synchronous mode to NORMAL for better performance
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Set temp store to memory
    cursor.execute("PRAGMA temp_store=memory")
    # Set mmap size to 256MB
    cursor.execute("PRAGMA mmap_size=268435456")
    cursor.close()


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str = None):
        """Initialize database manager.

        Args:
            database_url: Database connection URL. If None, uses settings.
        """
        self.database_url = database_url or settings.database_url
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()

    def _initialize_engine(self):
        """Initialize SQLAlchemy engine."""
        # SQLite-specific engine configuration
        if self.database_url.startswith("sqlite"):
            self.engine = create_engine(
                self.database_url,
                # Use StaticPool for SQLite to handle connection pooling
                poolclass=StaticPool,
                # Allow multiple threads to use the same connection
                pool_pre_ping=True,
                # Connection arguments
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                },
                # Echo SQL queries in debug mode
                echo=settings.debug,
            )
        else:
            # For other databases (if needed in future)
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                echo=settings.debug,
            )

        # Create sessionmaker
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        logger.info(f"Database engine initialized: {self.database_url}")

    def create_tables(self):
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {str(e)}")
            raise

    def drop_tables(self):
        """Drop all database tables (use with caution!)."""
        if settings.debug:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("Database tables dropped")
        else:
            logger.error("Table drop attempted in production mode - rejected")
            raise PermissionError("Cannot drop tables in production mode")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session context manager."""
        session = self.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """Get database session directly (caller must close)."""
        return self.SessionLocal()

    def health_check(self) -> bool:
        """Check database health."""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False

    def get_statistics(self) -> dict:
        """Get database statistics."""
        stats = {}
        try:
            with self.get_session() as session:
                # Get table row counts
                from app.models import (
                    AuditLog,
                    CacheEntry,
                    Document,
                    LockEntry,
                    RateLimitEntry,
                    Reference,
                    Repository,
                )
                from app.models import Session as UserSession
                from app.models import (
                    User,
                )

                tables = {
                    "documents": Document,
                    "references": Reference,
                    "repositories": Repository,
                    "users": User,
                    "sessions": UserSession,
                    "cache_entries": CacheEntry,
                    "rate_limit_entries": RateLimitEntry,
                    "lock_entries": LockEntry,
                    "audit_logs": AuditLog,
                }

                for table_name, model in tables.items():
                    count = session.query(model).count()
                    stats[f"{table_name}_count"] = count

                # Get database size (SQLite only)
                if self.database_url.startswith("sqlite"):
                    db_path = self.database_url.replace("sqlite:///", "")
                    if os.path.exists(db_path):
                        size = os.path.getsize(db_path)
                        stats["database_size_bytes"] = size
                        stats["database_size_mb"] = round(size / (1024 * 1024), 2)

        except Exception as e:
            logger.error(f"Failed to get database statistics: {str(e)}")
            stats["error"] = str(e)

        return stats

    def vacuum(self):
        """Optimize database (SQLite VACUUM)."""
        try:
            with self.get_session() as session:
                session.execute("VACUUM")
            logger.info("Database vacuum completed")
        except Exception as e:
            logger.error(f"Database vacuum failed: {str(e)}")
            raise

    def close(self):
        """Close database engine."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database engine closed")


# Global database manager instance
database_manager = DatabaseManager()


def get_database():
    """Get database manager instance."""
    return database_manager


def get_db_session():
    """Dependency for FastAPI to get database session."""
    with database_manager.get_session() as session:
        yield session


def init_database():
    """Initialize database with tables."""
    database_manager.create_tables()


def close_database():
    """Close database connections."""
    database_manager.close()
