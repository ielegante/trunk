"""In-memory cache manager to replace Redis dependencies."""

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union

from app.database import database_manager
from app.models import CacheEntry

logger = logging.getLogger(__name__)


@dataclass
class CacheItem:
    """Represents a cached item."""

    key: str
    value: Any
    created_at: float
    expires_at: Optional[float]
    size_bytes: int
    category: str
    access_count: int = 0
    last_accessed: float = 0


class MemoryCacheManager:
    """In-memory cache manager with LRU eviction and optional persistence."""

    def __init__(self, max_size_mb: int = 64, max_items: int = 10000):
        """Initialize cache manager.

        Args:
            max_size_mb: Maximum cache size in MB
            max_items: Maximum number of items in cache
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_items = max_items
        self.cache: Dict[str, CacheItem] = {}
        self.lock = threading.RLock()
        self.current_size = 0
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "errors": 0}

        # Background cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_expired_items, daemon=True
        )
        self.cleanup_thread.start()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            item = self.cache.get(key)
            if not item:
                self.stats["misses"] += 1
                return None

            # Check if expired
            if item.expires_at and time.time() > item.expires_at:
                self._remove_item(key)
                self.stats["misses"] += 1
                return None

            # Update access statistics
            item.access_count += 1
            item.last_accessed = time.time()
            self.stats["hits"] += 1

            return item.value

    def set(
        self, key: str, value: Any, ttl: Optional[int] = None, category: str = "general"
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            category: Category for organization

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                # Calculate size
                serialized = json.dumps(value) if not isinstance(value, str) else value
                size_bytes = len(serialized.encode("utf-8"))

                # Check if we need to make room
                if key not in self.cache:
                    self._ensure_capacity(size_bytes)

                # Remove old item if exists
                if key in self.cache:
                    self._remove_item(key)

                # Create new item
                expires_at = time.time() + ttl if ttl else None
                item = CacheItem(
                    key=key,
                    value=value,
                    created_at=time.time(),
                    expires_at=expires_at,
                    size_bytes=size_bytes,
                    category=category,
                    last_accessed=time.time(),
                )

                self.cache[key] = item
                self.current_size += size_bytes

                return True

        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            self.stats["errors"] += 1
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self.lock:
            if key in self.cache:
                self._remove_item(key)
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self.lock:
            item = self.cache.get(key)
            if not item:
                return False

            # Check if expired
            if item.expires_at and time.time() > item.expires_at:
                self._remove_item(key)
                return False

            return True

    def clear(self, category: Optional[str] = None) -> int:
        """Clear cache entries.

        Args:
            category: If specified, only clear entries from this category

        Returns:
            Number of items cleared
        """
        with self.lock:
            if category:
                keys_to_remove = [
                    key for key, item in self.cache.items() if item.category == category
                ]
            else:
                keys_to_remove = list(self.cache.keys())

            for key in keys_to_remove:
                self._remove_item(key)

            return len(keys_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            hit_rate = (
                self.stats["hits"] / (self.stats["hits"] + self.stats["misses"])
                if (self.stats["hits"] + self.stats["misses"]) > 0
                else 0
            )

            category_stats = {}
            for item in self.cache.values():
                cat = item.category
                if cat not in category_stats:
                    category_stats[cat] = {"count": 0, "size_mb": 0}
                category_stats[cat]["count"] += 1
                category_stats[cat]["size_mb"] += item.size_bytes / (1024 * 1024)

            return {
                "total_items": len(self.cache),
                "current_size_mb": round(self.current_size / (1024 * 1024), 2),
                "max_size_mb": round(self.max_size_bytes / (1024 * 1024), 2),
                "hit_rate": round(hit_rate, 3),
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "evictions": self.stats["evictions"],
                "errors": self.stats["errors"],
                "categories": category_stats,
            }

    def _ensure_capacity(self, additional_bytes: int):
        """Ensure cache has capacity for additional bytes."""
        # Check if we need to evict items
        while (
            len(self.cache) >= self.max_items
            or self.current_size + additional_bytes > self.max_size_bytes
        ):
            self._evict_lru_item()

    def _evict_lru_item(self):
        """Evict least recently used item."""
        if not self.cache:
            return

        # Find LRU item
        lru_key = min(self.cache.keys(), key=lambda k: self.cache[k].last_accessed)

        self._remove_item(lru_key)
        self.stats["evictions"] += 1

    def _remove_item(self, key: str):
        """Remove item from cache."""
        if key in self.cache:
            item = self.cache.pop(key)
            self.current_size -= item.size_bytes

    def _cleanup_expired_items(self):
        """Background thread to clean up expired items."""
        while True:
            try:
                time.sleep(60)  # Check every minute

                with self.lock:
                    current_time = time.time()
                    expired_keys = [
                        key
                        for key, item in self.cache.items()
                        if item.expires_at and current_time > item.expires_at
                    ]

                    for key in expired_keys:
                        self._remove_item(key)
                        self.stats["evictions"] += 1

            except Exception as e:
                logger.error(f"Cache cleanup error: {str(e)}")
                time.sleep(60)  # Wait before retrying


class GitOperationCache:
    """Cache for git operations to improve performance."""

    def __init__(self, cache_manager: MemoryCacheManager):
        self.cache = cache_manager
        self.category = "git_operations"

    def get_commit_info(
        self, repo_id: str, commit_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached commit information."""
        key = f"commit_info:{repo_id}:{commit_hash}"
        return self.cache.get(key)

    def set_commit_info(
        self,
        repo_id: str,
        commit_hash: str,
        commit_info: Dict[str, Any],
        ttl: int = 3600,
    ):
        """Cache commit information."""
        key = f"commit_info:{repo_id}:{commit_hash}"
        self.cache.set(key, commit_info, ttl, self.category)

    def get_file_content(
        self, repo_id: str, file_path: str, commit_hash: str
    ) -> Optional[str]:
        """Get cached file content."""
        key = f"file_content:{repo_id}:{file_path}:{commit_hash}"
        return self.cache.get(key)

    def set_file_content(
        self,
        repo_id: str,
        file_path: str,
        commit_hash: str,
        content: str,
        ttl: int = 1800,
    ):
        """Cache file content."""
        key = f"file_content:{repo_id}:{file_path}:{commit_hash}"
        self.cache.set(key, content, ttl, self.category)

    def get_diff(self, repo_id: str, from_commit: str, to_commit: str) -> Optional[str]:
        """Get cached diff."""
        key = f"diff:{repo_id}:{from_commit}:{to_commit}"
        return self.cache.get(key)

    def set_diff(
        self, repo_id: str, from_commit: str, to_commit: str, diff: str, ttl: int = 1800
    ):
        """Cache diff."""
        key = f"diff:{repo_id}:{from_commit}:{to_commit}"
        self.cache.set(key, diff, ttl, self.category)

    def invalidate_repo(self, repo_id: str):
        """Invalidate all cache entries for a repository."""
        # Since we can't easily pattern match, we'll clear the entire category
        # In a production system, you might want to implement pattern matching
        self.cache.clear(self.category)


class DocumentProcessingCache:
    """Cache for document processing operations."""

    def __init__(self, cache_manager: MemoryCacheManager):
        self.cache = cache_manager
        self.category = "document_processing"

    def get_processed_document(
        self, document_id: str, version: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached processed document."""
        key = f"processed_doc:{document_id}:{version}"
        return self.cache.get(key)

    def set_processed_document(
        self,
        document_id: str,
        version: str,
        processed_doc: Dict[str, Any],
        ttl: int = 3600,
    ):
        """Cache processed document."""
        key = f"processed_doc:{document_id}:{version}"
        self.cache.set(key, processed_doc, ttl, self.category)

    def get_document_analysis(
        self, document_id: str, analysis_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached document analysis."""
        key = f"analysis:{document_id}:{analysis_type}"
        return self.cache.get(key)

    def set_document_analysis(
        self,
        document_id: str,
        analysis_type: str,
        analysis: Dict[str, Any],
        ttl: int = 7200,
    ):
        """Cache document analysis."""
        key = f"analysis:{document_id}:{analysis_type}"
        self.cache.set(key, analysis, ttl, self.category)

    def get_references(self, document_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached document references."""
        key = f"references:{document_id}"
        return self.cache.get(key)

    def set_references(
        self, document_id: str, references: List[Dict[str, Any]], ttl: int = 1800
    ):
        """Cache document references."""
        key = f"references:{document_id}"
        self.cache.set(key, references, ttl, self.category)

    def invalidate_document(self, document_id: str):
        """Invalidate all cache entries for a document."""
        # Clear entire category since we can't pattern match easily
        self.cache.clear(self.category)


class PersistentCacheManager:
    """Manages persistent cache entries in SQLite database."""

    def __init__(self):
        self.db = database_manager

    def get(self, key: str) -> Optional[Any]:
        """Get value from persistent cache."""
        try:
            with self.db.get_session() as session:
                entry = session.query(CacheEntry).filter_by(key=key).first()
                if not entry:
                    return None

                # Check if expired
                if entry.expires_at and datetime.utcnow() > entry.expires_at:
                    session.delete(entry)
                    session.commit()
                    return None

                return json.loads(entry.value)

        except Exception as e:
            logger.error(f"Persistent cache get error: {str(e)}")
            return None

    def set(
        self, key: str, value: Any, ttl: Optional[int] = None, category: str = "general"
    ) -> bool:
        """Set value in persistent cache."""
        try:
            with self.db.get_session() as session:
                # Remove existing entry
                existing = session.query(CacheEntry).filter_by(key=key).first()
                if existing:
                    session.delete(existing)

                # Create new entry
                serialized = json.dumps(value)
                expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None

                entry = CacheEntry(
                    key=key,
                    value=serialized,
                    expires_at=expires_at,
                    category=category,
                    size_bytes=len(serialized.encode("utf-8")),
                )

                session.add(entry)
                session.commit()
                return True

        except Exception as e:
            logger.error(f"Persistent cache set error: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from persistent cache."""
        try:
            with self.db.get_session() as session:
                entry = session.query(CacheEntry).filter_by(key=key).first()
                if entry:
                    session.delete(entry)
                    session.commit()
                    return True
                return False

        except Exception as e:
            logger.error(f"Persistent cache delete error: {str(e)}")
            return False

    def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        try:
            with self.db.get_session() as session:
                expired_entries = (
                    session.query(CacheEntry)
                    .filter(CacheEntry.expires_at < datetime.utcnow())
                    .all()
                )

                count = len(expired_entries)
                for entry in expired_entries:
                    session.delete(entry)

                session.commit()
                return count

        except Exception as e:
            logger.error(f"Persistent cache cleanup error: {str(e)}")
            return 0


# Global cache instances
memory_cache = MemoryCacheManager()
git_cache = GitOperationCache(memory_cache)
document_cache = DocumentProcessingCache(memory_cache)
persistent_cache = PersistentCacheManager()
