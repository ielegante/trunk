"""
Advanced caching strategies for backend performance optimization
"""

import asyncio
import hashlib
import json
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import redis

logger = logging.getLogger(__name__)


class CacheManager:
    """Centralized cache management with multiple strategies"""

    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.stats = {"hits": 0, "misses": 0, "errors": 0}

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = {"args": args, "kwargs": {k: v for k, v in sorted(kwargs.items())}}
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self.redis.get(key)
            if value:
                self.stats["hits"] += 1
                return json.loads(value)
            else:
                self.stats["misses"] += 1
                return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats["errors"] += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats["errors"] += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            self.stats["errors"] += 1
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            self.stats["errors"] += 1
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests) if total_requests > 0 else 0

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "errors": self.stats["errors"],
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }


class GitOperationCache:
    """Specialized cache for Git operations"""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.ttl = 1800  # 30 minutes for git operations

    async def get_repository_info(self, repo_id: str) -> Optional[Dict]:
        """Get cached repository information"""
        key = f"repo_info:{repo_id}"
        return await self.cache.get(key)

    async def set_repository_info(self, repo_id: str, info: Dict) -> bool:
        """Cache repository information"""
        key = f"repo_info:{repo_id}"
        return await self.cache.set(key, info, self.ttl)

    async def get_commit_history(
        self, repo_id: str, branch: str, limit: int = 50
    ) -> Optional[List]:
        """Get cached commit history"""
        key = f"commit_history:{repo_id}:{branch}:{limit}"
        return await self.cache.get(key)

    async def set_commit_history(
        self, repo_id: str, branch: str, commits: List, limit: int = 50
    ) -> bool:
        """Cache commit history"""
        key = f"commit_history:{repo_id}:{branch}:{limit}"
        return await self.cache.set(key, commits, self.ttl)

    async def get_file_content(
        self, repo_id: str, file_path: str, commit_hash: str
    ) -> Optional[str]:
        """Get cached file content"""
        key = f"file_content:{repo_id}:{file_path}:{commit_hash}"
        return await self.cache.get(key)

    async def set_file_content(
        self, repo_id: str, file_path: str, commit_hash: str, content: str
    ) -> bool:
        """Cache file content"""
        key = f"file_content:{repo_id}:{file_path}:{commit_hash}"
        return await self.cache.set(
            key, content, self.ttl * 2
        )  # Longer TTL for file content

    async def invalidate_repository(self, repo_id: str) -> int:
        """Invalidate all cache entries for a repository"""
        patterns = [
            f"repo_info:{repo_id}",
            f"commit_history:{repo_id}:*",
            f"file_content:{repo_id}:*",
        ]

        total_cleared = 0
        for pattern in patterns:
            total_cleared += await self.cache.clear_pattern(pattern)

        return total_cleared


class DocumentProcessingCache:
    """Specialized cache for document processing operations"""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.ttl = 7200  # 2 hours for document processing

    async def get_document_conversion(
        self, doc_id: str, format_type: str
    ) -> Optional[Dict]:
        """Get cached document conversion"""
        key = f"doc_conversion:{doc_id}:{format_type}"
        return await self.cache.get(key)

    async def set_document_conversion(
        self, doc_id: str, format_type: str, result: Dict
    ) -> bool:
        """Cache document conversion result"""
        key = f"doc_conversion:{doc_id}:{format_type}"
        return await self.cache.set(key, result, self.ttl)

    async def get_pdf_extraction(self, pdf_hash: str) -> Optional[Dict]:
        """Get cached PDF extraction"""
        key = f"pdf_extraction:{pdf_hash}"
        return await self.cache.get(key)

    async def set_pdf_extraction(self, pdf_hash: str, result: Dict) -> bool:
        """Cache PDF extraction result"""
        key = f"pdf_extraction:{pdf_hash}"
        return await self.cache.set(
            key, result, self.ttl * 2
        )  # Longer TTL for PDF processing


def cache_result(
    prefix: str, ttl: Optional[int] = None, key_func: Optional[Callable] = None
):
    """Decorator to cache function results"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache manager from first argument (usually self)
            cache_manager = getattr(args[0], "cache_manager", None)
            if not cache_manager:
                # If no cache manager, execute function normally
                return await func(*args, **kwargs)

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache_manager._generate_key(prefix, *args[1:], **kwargs)

            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_manager.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


class PerformanceMonitor:
    """Monitor and optimize performance metrics"""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.metrics = {"slow_queries": [], "cache_performance": {}, "memory_usage": []}

    def log_slow_query(self, query: str, duration: float, threshold: float = 1.0):
        """Log slow database queries"""
        if duration > threshold:
            self.metrics["slow_queries"].append(
                {"query": query, "duration": duration, "timestamp": time.time()}
            )

            # Keep only last 100 slow queries
            if len(self.metrics["slow_queries"]) > 100:
                self.metrics["slow_queries"] = self.metrics["slow_queries"][-100:]

    async def get_cache_performance(self) -> Dict[str, Any]:
        """Get comprehensive cache performance metrics"""
        stats = self.cache.get_stats()

        # Get Redis memory usage
        try:
            redis_info = await self.cache.redis.info("memory")
            memory_stats = {
                "used_memory": redis_info.get("used_memory", 0),
                "used_memory_human": redis_info.get("used_memory_human", "0B"),
                "used_memory_peak": redis_info.get("used_memory_peak", 0),
                "used_memory_peak_human": redis_info.get(
                    "used_memory_peak_human", "0B"
                ),
            }
        except Exception:
            memory_stats = {}

        return {
            "cache_stats": stats,
            "memory_stats": memory_stats,
            "slow_queries": len(self.metrics["slow_queries"]),
            "recommendations": self._get_performance_recommendations(stats),
        }

    def _get_performance_recommendations(self, stats: Dict) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []

        if stats["hit_rate"] < 0.7:
            recommendations.append(
                "Low cache hit rate - consider increasing TTL or optimizing cache keys"
            )

        if stats["errors"] > stats["hits"] * 0.1:
            recommendations.append("High cache error rate - check Redis connectivity")

        if len(self.metrics["slow_queries"]) > 10:
            recommendations.append(
                "Multiple slow queries detected - consider query optimization"
            )

        return recommendations


# Global cache instances (initialized in main.py)
cache_manager: Optional[CacheManager] = None
git_cache: Optional[GitOperationCache] = None
doc_cache: Optional[DocumentProcessingCache] = None
performance_monitor: Optional[PerformanceMonitor] = None
