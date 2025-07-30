"""SQLAlchemy models for Trunk Legal Git."""

import json
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

# Typing imports removed - not used in this file


Base = declarative_base()


class JSONString(TypeDecorator):
    """Custom JSON type that handles serialization/deserialization."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value


class ReferenceType(Enum):
    """Types of document references."""

    CITATION = "citation"
    AMENDMENT = "amendment"
    SUPERSEDES = "supersedes"
    INCORPORATES = "incorporates"
    RELATED = "related"
    PARENT = "parent"
    CHILD = "child"
    EXHIBIT = "exhibit"
    ATTACHMENT = "attachment"
    CROSS_REFERENCE = "cross_re"
    EXTERNAL = "external"


class ReferenceStatus(Enum):
    """Status of a reference."""

    VALID = "valid"
    BROKEN = "broken"
    OUTDATED = "outdated"
    PENDING = "pending"
    RESOLVED = "resolved"


class Document(Base):
    """Document model for storing document metadata."""

    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), nullable=False)
    file_path = Column(String(512), nullable=False)
    title = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    content_hash = Column(String(64), nullable=False)
    document_type = Column(String(50), nullable=False)
    doc_metadata = Column(JSONString, nullable=False, default={})

    # Relationships
    outgoing_references = relationship(
        "Reference",
        foreign_keys="Reference.source_doc_id",
        back_populates="source_document",
        cascade="all, delete-orphan",
    )
    incoming_references = relationship(
        "Reference",
        foreign_keys="Reference.target_doc_id",
        back_populates="target_document",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("ix_documents_repository_id", "repository_id"),
        Index("ix_documents_file_path", "file_path"),
        Index("ix_documents_content_hash", "content_hash"),
        Index("ix_documents_updated_at", "updated_at"),
    )


class Reference(Base):
    """Reference model for storing document relationships."""

    __tablename__ = "references"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_doc_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    target_doc_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    reference_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="valid")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    location = Column(JSONString, nullable=False, default={})
    context = Column(Text, nullable=True)
    doc_metadata = Column(JSONString, nullable=False, default={})

    # Relationships
    source_document = relationship(
        "Document", foreign_keys=[source_doc_id], back_populates="outgoing_references"
    )
    target_document = relationship(
        "Document", foreign_keys=[target_doc_id], back_populates="incoming_references"
    )

    # Indexes
    __table_args__ = (
        Index("ix_references_source_doc_id", "source_doc_id"),
        Index("ix_references_target_doc_id", "target_doc_id"),
        Index("ix_references_reference_type", "reference_type"),
        Index("ix_references_status", "status"),
        Index("ix_references_updated_at", "updated_at"),
    )


class Repository(Base):
    """Repository model for storing repository metadata."""

    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_private = Column(String(10), nullable=False, default="true")
    settings = Column(JSONString, nullable=False, default={})

    # Indexes
    __table_args__ = (
        Index("ix_repositories_owner_id", "owner_id"),
        Index("ix_repositories_name", "name"),
        Index("ix_repositories_updated_at", "updated_at"),
    )


class User(Base):
    """User model for storing user authentication data."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    google_id = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    picture = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_login = Column(DateTime, nullable=True)
    is_active = Column(String(10), nullable=False, default="true")
    settings = Column(JSONString, nullable=False, default={})

    # Indexes
    __table_args__ = (
        Index("ix_users_google_id", "google_id"),
        Index("ix_users_email", "email"),
        Index("ix_users_last_login", "last_login"),
    )


class Session(Base):
    """Session model for storing user session data."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(String(10), nullable=False, default="true")
    doc_metadata = Column(JSONString, nullable=False, default={})

    # Indexes
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_token", "token"),
        Index("ix_sessions_expires_at", "expires_at"),
    )


class CacheEntry(Base):
    """Cache entry model for in-memory caching replacement."""

    __tablename__ = "cache_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(255), nullable=False, unique=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    category = Column(String(50), nullable=False, default="general")
    size_bytes = Column(Integer, nullable=False, default=0)

    # Indexes
    __table_args__ = (
        Index("ix_cache_entries_key", "key"),
        Index("ix_cache_entries_category", "category"),
        Index("ix_cache_entries_expires_at", "expires_at"),
    )


class RateLimitEntry(Base):
    """Rate limit entry model for tracking request limits."""

    __tablename__ = "rate_limit_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String(255), nullable=False)  # IP address or user ID
    request_count = Column(Integer, nullable=False, default=0)
    window_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    window_end = Column(DateTime, nullable=False)
    category = Column(String(50), nullable=False, default="general")

    # Indexes
    __table_args__ = (
        Index("ix_rate_limit_entries_identifier", "identifier"),
        Index("ix_rate_limit_entries_window_end", "window_end"),
        Index("ix_rate_limit_entries_category", "category"),
    )


class LockEntry(Base):
    """Lock entry model for distributed locking replacement."""

    __tablename__ = "lock_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resource_id = Column(String(255), nullable=False, unique=True)
    owner_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    lock_type = Column(String(50), nullable=False, default="document")
    doc_metadata = Column(JSONString, nullable=False, default={})

    # Indexes
    __table_args__ = (
        Index("ix_lock_entries_resource_id", "resource_id"),
        Index("ix_lock_entries_owner_id", "owner_id"),
        Index("ix_lock_entries_expires_at", "expires_at"),
    )


class AuditLog(Base):
    """Audit log model for tracking system events."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    details = Column(JSONString, nullable=False, default={})
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_timestamp", "timestamp"),
    )
