"""Advanced caching system for document processing optimization."""

import gc
import hashlib
import json
import logging
import pickle
import threading
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single cache entry."""

    key: str
    value: Any
    size_bytes: int
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl_seconds is None:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)

    def update_access(self):
        """Update access timestamp and count."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class CacheStorage:
    """Abstract base class for cache storage backends."""

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache."""
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store value in cache."""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """Remove value from cache."""
        raise NotImplementedError

    def clear(self) -> int:
        """Clear all cache entries."""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        raise NotImplementedError


class MemoryCache(CacheStorage):
    """In-memory cache implementation with LRU eviction."""

    def __init__(self, max_size_mb: int = 100, max_entries: int = 1000):
        """Initialize memory cache.

        Args:
            max_size_mb: Maximum cache size in megabytes
            max_entries: Maximum number of cache entries
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_entries = max_entries
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.current_size_bytes = 0
        self.lock = threading.RLock()
        self.hit_count = 0
        self.miss_count = 0
        self._eviction_count = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache."""
        with self.lock:
            if key not in self.cache:
                self.miss_count += 1
                return None

            entry = self.cache[key]

            # Check expiration
            if entry.is_expired():
                self._remove_entry(key)
                self.miss_count += 1
                return None

            # Update LRU order
            self.cache.move_to_end(key)
            entry.update_access()
            self.hit_count += 1

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store value in cache."""
        with self.lock:
            # Calculate size
            size_bytes = self._estimate_size(value)

            # Check if value is too large
            if size_bytes > self.max_size_bytes:
                logger.warning(f"Value too large for cache: {size_bytes} bytes")
                return False

            # Remove existing entry if present
            if key in self.cache:
                self._remove_entry(key)

            # Evict entries if necessary
            while (
                self.current_size_bytes + size_bytes > self.max_size_bytes
                or len(self.cache) >= self.max_entries
            ):
                if not self._evict_lru():
                    break

            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                size_bytes=size_bytes,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=0,
                ttl_seconds=ttl,
            )

            self.cache[key] = entry
            self.current_size_bytes += size_bytes

            return True

    def delete(self, key: str) -> bool:
        """Remove value from cache."""
        with self.lock:
            return self._remove_entry(key)

    def clear(self) -> int:
        """Clear all cache entries."""
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            self.current_size_bytes = 0
            gc.collect()  # Force garbage collection
            return count

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self.lock:
            if key not in self.cache:
                return False

            entry = self.cache[key]
            if entry.is_expired():
                self._remove_entry(key)
                return False

            return True

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = self.hit_count / total_requests if total_requests > 0 else 0

            return {
                "entries": len(self.cache),
                "size_bytes": self.current_size_bytes,
                "size_mb": self.current_size_bytes / (1024 * 1024),
                "max_size_mb": self.max_size_bytes / (1024 * 1024),
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "hit_rate": hit_rate,
                "eviction_count": self._eviction_count,
            }

    def _remove_entry(self, key: str) -> bool:
        """Remove entry from cache."""
        if key in self.cache:
            entry = self.cache[key]
            self.current_size_bytes -= entry.size_bytes
            del self.cache[key]
            return True
        return False

    def _evict_lru(self) -> bool:
        """Evict least recently used entry."""
        if not self.cache:
            return False

        # Get oldest entry (first in OrderedDict)
        key, entry = next(iter(self.cache.items()))
        self._remove_entry(key)
        self._eviction_count += 1

        logger.debug(f"Evicted cache entry: {key}")
        return True

    def _estimate_size(self, value: Any) -> int:
        """Estimate size of value in bytes."""
        try:
            # Try pickling for accurate size
            return len(pickle.dumps(value))
        except Exception:
            # Fallback to string representation
            return len(str(value).encode("utf-8"))


class FileCache(CacheStorage):
    """File-based cache implementation for persistence."""

    def __init__(self, cache_dir: Path, max_size_mb: int = 1000):
        """Initialize file cache.

        Args:
            cache_dir: Directory for cache files
            max_size_mb: Maximum cache size in megabytes
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.index_file = self.cache_dir / ".cache_index.json"
        self.lock = threading.RLock()
        self._load_index()

    def _load_index(self):
        """Load cache index from disk."""
        with self.lock:
            if self.index_file.exists():
                try:
                    with open(self.index_file, "r") as f:
                        index_data = json.load(f)
                        self.index = {k: CacheEntry(**v) for k, v in index_data.items()}
                        # Convert timestamp strings back to datetime
                        for entry in self.index.values():
                            entry.created_at = datetime.fromisoformat(entry.created_at)
                            entry.last_accessed = datetime.fromisoformat(
                                entry.last_accessed
                            )
                except Exception as e:
                    logger.error(f"Failed to load cache index: {e}")
                    self.index = {}
            else:
                self.index = {}

    def _save_index(self):
        """Save cache index to disk."""
        with self.lock:
            try:
                index_data = {}
                for k, v in self.index.items():
                    entry_dict = asdict(v)
                    # Convert datetime to string
                    entry_dict["created_at"] = v.created_at.isoformat()
                    entry_dict["last_accessed"] = v.last_accessed.isoformat()
                    # Don't save the actual value
                    del entry_dict["value"]
                    index_data[k] = entry_dict

                with open(self.index_file, "w") as f:
                    json.dump(index_data, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save cache index: {e}")

    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key."""
        # Use hash to avoid filesystem issues with special characters
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache."""
        with self.lock:
            if key not in self.index:
                return None

            entry = self.index[key]

            # Check expiration
            if entry.is_expired():
                self.delete(key)
                return None

            # Load from file
            cache_file = self._get_cache_file(key)
            if not cache_file.exists():
                # Index out of sync, remove entry
                del self.index[key]
                return None

            try:
                with open(cache_file, "rb") as f:
                    value = pickle.load(f)

                entry.update_access()
                self._save_index()
                return value

            except Exception as e:
                logger.error(f"Failed to load cache file: {e}")
                self.delete(key)
                return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store value in cache."""
        with self.lock:
            try:
                # Serialize value
                serialized = pickle.dumps(value)
                size_bytes = len(serialized)

                # Check size
                if size_bytes > self.max_size_bytes:
                    logger.warning(f"Value too large for cache: {size_bytes} bytes")
                    return False

                # Evict if necessary
                current_size = self._get_total_size()
                while current_size + size_bytes > self.max_size_bytes:
                    if not self._evict_oldest():
                        break
                    current_size = self._get_total_size()

                # Write to file
                cache_file = self._get_cache_file(key)
                with open(cache_file, "wb") as f:
                    f.write(serialized)

                # Update index
                entry = CacheEntry(
                    key=key,
                    value=None,  # Don't store in memory
                    size_bytes=size_bytes,
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                    access_count=0,
                    ttl_seconds=ttl,
                )

                self.index[key] = entry
                self._save_index()

                return True

            except Exception as e:
                logger.error(f"Failed to cache value: {e}")
                return False

    def delete(self, key: str) -> bool:
        """Remove value from cache."""
        with self.lock:
            if key not in self.index:
                return False

            # Remove file
            cache_file = self._get_cache_file(key)
            try:
                cache_file.unlink(missing_ok=True)
            except Exception as e:
                logger.error(f"Failed to delete cache file: {e}")

            # Remove from index
            del self.index[key]
            self._save_index()

            return True

    def clear(self) -> int:
        """Clear all cache entries."""
        with self.lock:
            count = len(self.index)

            # Remove all cache files
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.error(f"Failed to delete cache file: {e}")

            # Clear index
            self.index.clear()
            self._save_index()

            return count

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self.lock:
            if key not in self.index:
                return False

            entry = self.index[key]
            if entry.is_expired():
                self.delete(key)
                return False

            # Check if file exists
            cache_file = self._get_cache_file(key)
            if not cache_file.exists():
                del self.index[key]
                return False

            return True

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_size = self._get_total_size()

            return {
                "entries": len(self.index),
                "size_bytes": total_size,
                "size_mb": total_size / (1024 * 1024),
                "max_size_mb": self.max_size_bytes / (1024 * 1024),
                "cache_dir": str(self.cache_dir),
            }

    def _get_total_size(self) -> int:
        """Calculate total size of cached files."""
        total_size = 0
        for entry in self.index.values():
            total_size += entry.size_bytes
        return total_size

    def _evict_oldest(self) -> bool:
        """Evict oldest entry."""
        if not self.index:
            return False

        # Find oldest entry
        oldest_key = min(self.index.keys(), key=lambda k: self.index[k].last_accessed)

        self.delete(oldest_key)
        logger.debug(f"Evicted cache entry: {oldest_key}")
        return True


class CacheManager:
    """High-level cache management with multiple backends."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize cache manager.

        Args:
            config: Cache configuration
        """
        self.config = config or {}

        # Initialize caches
        self.memory_cache = MemoryCache(
            max_size_mb=self.config.get("memory_cache_mb", 100),
            max_entries=self.config.get("memory_cache_entries", 1000),
        )

        # File cache for persistence
        cache_dir = Path(self.config.get("cache_dir", ".cache"))
        self.file_cache = FileCache(
            cache_dir=cache_dir, max_size_mb=self.config.get("file_cache_mb", 1000)
        )

        # Cache statistics
        self.stats = {
            "memory_hits": 0,
            "file_hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache, checking memory then file cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        # Check memory cache first
        value = self.memory_cache.get(key)
        if value is not None:
            self.stats["memory_hits"] += 1
            return value

        # Check file cache
        value = self.file_cache.get(key)
        if value is not None:
            self.stats["file_hits"] += 1
            # Promote to memory cache
            self.memory_cache.set(key, value)
            return value

        self.stats["misses"] += 1
        return default

    def set(
        self, key: str, value: Any, ttl: Optional[int] = None, persist: bool = True
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            persist: Whether to persist to file cache

        Returns:
            True if successful
        """
        self.stats["sets"] += 1

        # Always set in memory cache
        memory_success = self.memory_cache.set(key, value, ttl)

        # Optionally persist to file
        if persist:
            file_success = self.file_cache.set(key, value, ttl)
            return memory_success and file_success

        return memory_success

    def delete(self, key: str) -> bool:
        """Delete value from all caches.

        Args:
            key: Cache key

        Returns:
            True if deleted from any cache
        """
        self.stats["deletes"] += 1

        memory_deleted = self.memory_cache.delete(key)
        file_deleted = self.file_cache.delete(key)

        return memory_deleted or file_deleted

    def clear(self) -> int:
        """Clear all caches.

        Returns:
            Total number of entries cleared
        """
        memory_cleared = self.memory_cache.clear()
        file_cleared = self.file_cache.clear()

        return memory_cleared + file_cleared

    def exists(self, key: str) -> bool:
        """Check if key exists in any cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        return self.memory_cache.exists(key) or self.file_cache.exists(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics.

        Returns:
            Dictionary of cache statistics
        """
        return {
            "manager_stats": self.stats,
            "memory_cache": self.memory_cache.get_stats(),
            "file_cache": self.file_cache.get_stats(),
        }


class DocumentCache:
    """Specialized cache for document processing results."""

    def __init__(self, cache_manager: CacheManager):
        """Initialize document cache.

        Args:
            cache_manager: Cache manager instance
        """
        self.cache_manager = cache_manager

    def cache_key(
        self, doc_id: str, operation: str, params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate cache key for document operation.

        Args:
            doc_id: Document identifier
            operation: Operation name (e.g., 'convert', 'extract')
            params: Operation parameters

        Returns:
            Cache key string
        """
        key_parts = [doc_id, operation]

        if params:
            # Sort params for consistent keys
            param_str = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key_parts.append(param_hash)

        return ":".join(key_parts)

    def get_conversion(
        self, doc_id: str, target_format: str, options: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Get cached document conversion.

        Args:
            doc_id: Document identifier
            target_format: Target format (e.g., 'markdown')
            options: Conversion options

        Returns:
            Cached conversion result or None
        """
        key = self.cache_key(doc_id, f"convert_{target_format}", options)
        return self.cache_manager.get(key)

    def set_conversion(
        self,
        doc_id: str,
        target_format: str,
        result: str,
        options: Optional[Dict[str, Any]] = None,
        ttl: int = 3600,
    ) -> bool:
        """Cache document conversion result.

        Args:
            doc_id: Document identifier
            target_format: Target format
            result: Conversion result
            options: Conversion options
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            True if cached successfully
        """
        key = self.cache_key(doc_id, f"convert_{target_format}", options)
        return self.cache_manager.set(key, result, ttl=ttl)

    def get_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get cached document metadata.

        Args:
            doc_id: Document identifier

        Returns:
            Cached metadata or None
        """
        key = self.cache_key(doc_id, "metadata")
        return self.cache_manager.get(key)

    def set_metadata(
        self, doc_id: str, metadata: Dict[str, Any], ttl: int = 7200
    ) -> bool:
        """Cache document metadata.

        Args:
            doc_id: Document identifier
            metadata: Document metadata
            ttl: Time to live in seconds (default: 2 hours)

        Returns:
            True if cached successfully
        """
        key = self.cache_key(doc_id, "metadata")
        return self.cache_manager.set(key, metadata, ttl=ttl)

    def invalidate_document(self, doc_id: str) -> int:
        """Invalidate all cached data for a document.

        Args:
            doc_id: Document identifier

        Returns:
            Number of cache entries invalidated
        """
        # This is a simplified implementation
        # In production, we'd need to track all keys for a document
        count = 0

        # Common operations to invalidate
        operations = [
            "metadata",
            "convert_markdown",
            "convert_html",
            "extract_text",
            "extract_structure",
        ]

        for operation in operations:
            key = self.cache_key(doc_id, operation)
            if self.cache_manager.delete(key):
                count += 1

        return count


def cached(
    cache_manager: CacheManager,
    key_func: Optional[Callable] = None,
    ttl: int = 3600,
    persist: bool = True,
):
    """Decorator for caching function results.

    Args:
        cache_manager: Cache manager instance
        key_func: Function to generate cache key from arguments
        ttl: Time to live in seconds
        persist: Whether to persist to file cache

    Returns:
        Decorator function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            # Check cache
            result = cache_manager.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return result

            # Call function
            result = func(*args, **kwargs)

            # Cache result
            cache_manager.set(cache_key, result, ttl=ttl, persist=persist)

            return result

        return wrapper

    return decorator
