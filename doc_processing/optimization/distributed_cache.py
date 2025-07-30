"""Distributed caching system for multi-instance document processing deployments."""

import asyncio
import hashlib
import json
import logging
import pickle
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class CacheNode:
    """Represents a cache node in the distributed system."""

    node_id: str
    host: str
    port: int
    is_active: bool = True
    last_heartbeat: Optional[datetime] = None
    capacity_mb: float = 1000.0
    used_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        if self.last_heartbeat:
            data["last_heartbeat"] = self.last_heartbeat.isoformat()
        return data


@dataclass
class CacheEntry:
    """Distributed cache entry with metadata."""

    key: str
    value: Any
    size_bytes: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    node_id: Optional[str] = None
    version: int = 1

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        if self.expires_at:
            data["expires_at"] = self.expires_at.isoformat()
        if self.last_accessed:
            data["last_accessed"] = self.last_accessed.isoformat()
        # Don't serialize the actual value in metadata
        del data["value"]
        return data


class ConsistentHashRing:
    """Consistent hash ring for distributed cache key distribution."""

    def __init__(self, nodes: List[CacheNode], replicas: int = 3):
        """Initialize consistent hash ring.

        Args:
            nodes: List of cache nodes
            replicas: Number of virtual nodes per physical node
        """
        self.nodes = {node.node_id: node for node in nodes}
        self.replicas = replicas
        self.ring = {}
        self._build_ring()

    def _build_ring(self):
        """Build the consistent hash ring."""
        self.ring = {}

        for node_id, node in self.nodes.items():
            for i in range(self.replicas):
                virtual_key = f"{node_id}:{i}"
                hash_key = self._hash(virtual_key)
                self.ring[hash_key] = node_id

    def _hash(self, key: str) -> int:
        """Generate hash for key."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def get_node(self, key: str) -> Optional[CacheNode]:
        """Get the node responsible for a key."""
        if not self.ring:
            return None

        hash_key = self._hash(key)

        # Find the first node clockwise from the hash
        for ring_key in sorted(self.ring.keys()):
            if hash_key <= ring_key:
                node_id = self.ring[ring_key]
                return self.nodes.get(node_id)

        # Wrap around to the first node
        first_key = min(self.ring.keys())
        node_id = self.ring[first_key]
        return self.nodes.get(node_id)

    def get_nodes(self, key: str, count: int = 1) -> List[CacheNode]:
        """Get multiple nodes for key (for replication)."""
        if not self.ring or count <= 0:
            return []

        hash_key = self._hash(key)
        nodes = []
        seen_nodes = set()

        sorted_keys = sorted(self.ring.keys())
        start_idx = 0

        # Find starting position
        for i, ring_key in enumerate(sorted_keys):
            if hash_key <= ring_key:
                start_idx = i
                break

        # Collect nodes, wrapping around if necessary
        for i in range(len(sorted_keys)):
            idx = (start_idx + i) % len(sorted_keys)
            ring_key = sorted_keys[idx]
            node_id = self.ring[ring_key]

            if node_id not in seen_nodes:
                node = self.nodes.get(node_id)
                if node and node.is_active:
                    nodes.append(node)
                    seen_nodes.add(node_id)

                    if len(nodes) >= count:
                        break

        return nodes

    def add_node(self, node: CacheNode):
        """Add a new node to the ring."""
        self.nodes[node.node_id] = node
        self._build_ring()

    def remove_node(self, node_id: str):
        """Remove a node from the ring."""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self._build_ring()

    def get_all_nodes(self) -> List[CacheNode]:
        """Get all nodes in the ring."""
        return list(self.nodes.values())


class DistributedCacheClient:
    """Client for distributed cache operations."""

    def __init__(self, nodes: List[CacheNode], replication_factor: int = 2):
        """Initialize distributed cache client.

        Args:
            nodes: List of cache nodes
            replication_factor: Number of replicas per key
        """
        self.hash_ring = ConsistentHashRing(nodes)
        self.replication_factor = replication_factor
        self.local_cache = {}  # Local cache for frequently accessed items
        self.local_cache_size = 0
        self.max_local_cache_mb = 50
        self.lock = threading.RLock()

        # Statistics
        self.stats = {
            "gets": 0,
            "sets": 0,
            "deletes": 0,
            "local_hits": 0,
            "remote_hits": 0,
            "misses": 0,
            "replication_failures": 0,
        }

    async def get(self, key: str) -> Optional[Any]:
        """Get value from distributed cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        with self.lock:
            self.stats["gets"] += 1

        # Check local cache first
        if key in self.local_cache:
            entry = self.local_cache[key]
            if not entry.is_expired():
                with self.lock:
                    self.stats["local_hits"] += 1
                return entry.value
            else:
                # Remove expired entry
                del self.local_cache[key]
                self.local_cache_size -= entry.size_bytes

        # Get from remote nodes
        nodes = self.hash_ring.get_nodes(key, self.replication_factor)

        for node in nodes:
            try:
                value = await self._get_from_node(node, key)
                if value is not None:
                    with self.lock:
                        self.stats["remote_hits"] += 1

                    # Cache locally for future access
                    self._cache_locally(key, value)
                    return value
            except Exception as e:
                logger.error(f"Failed to get from node {node.node_id}: {e}")
                continue

        with self.lock:
            self.stats["misses"] += 1
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in distributed cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        with self.lock:
            self.stats["sets"] += 1

        # Calculate size
        try:
            serialized = pickle.dumps(value)
            size_bytes = len(serialized)
        except Exception as e:
            logger.error(f"Failed to serialize value for key {key}: {e}")
            return False

        # Create cache entry
        expires_at = None
        if ttl:
            expires_at = datetime.now() + timedelta(seconds=ttl)

        entry = CacheEntry(
            key=key,
            value=value,
            size_bytes=size_bytes,
            created_at=datetime.now(),
            expires_at=expires_at,
        )

        # Get target nodes
        nodes = self.hash_ring.get_nodes(key, self.replication_factor)

        # Attempt to set on all replica nodes
        successful_sets = 0
        for node in nodes:
            try:
                success = await self._set_on_node(node, entry)
                if success:
                    successful_sets += 1
            except Exception as e:
                logger.error(f"Failed to set on node {node.node_id}: {e}")
                with self.lock:
                    self.stats["replication_failures"] += 1

        # Consider successful if we wrote to at least one node
        if successful_sets > 0:
            # Update local cache
            self._cache_locally(key, value, entry)
            return True

        return False

    async def delete(self, key: str) -> bool:
        """Delete value from distributed cache.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        with self.lock:
            self.stats["deletes"] += 1

        # Remove from local cache
        if key in self.local_cache:
            entry = self.local_cache[key]
            del self.local_cache[key]
            self.local_cache_size -= entry.size_bytes

        # Delete from remote nodes
        nodes = self.hash_ring.get_nodes(key, self.replication_factor)

        successful_deletes = 0
        for node in nodes:
            try:
                success = await self._delete_from_node(node, key)
                if success:
                    successful_deletes += 1
            except Exception as e:
                logger.error(f"Failed to delete from node {node.node_id}: {e}")

        return successful_deletes > 0

    async def _get_from_node(self, node: CacheNode, key: str) -> Optional[Any]:
        """Get value from specific node."""
        # This would implement the actual network call to the cache node
        # For now, return None to simulate a miss
        return None

    async def _set_on_node(self, node: CacheNode, entry: CacheEntry) -> bool:
        """Set value on specific node."""
        # This would implement the actual network call to the cache node
        # For now, return True to simulate success
        return True

    async def _delete_from_node(self, node: CacheNode, key: str) -> bool:
        """Delete value from specific node."""
        # This would implement the actual network call to the cache node
        # For now, return True to simulate success
        return True

    def _cache_locally(self, key: str, value: Any, entry: Optional[CacheEntry] = None):
        """Cache value locally for fast access."""
        if entry is None:
            try:
                serialized = pickle.dumps(value)
                size_bytes = len(serialized)
            except Exception:
                return

            entry = CacheEntry(
                key=key, value=value, size_bytes=size_bytes, created_at=datetime.now()
            )

        # Check if we have space
        max_size_bytes = self.max_local_cache_mb * 1024 * 1024
        if self.local_cache_size + entry.size_bytes > max_size_bytes:
            self._evict_local_cache()

        # Add to local cache
        self.local_cache[key] = entry
        self.local_cache_size += entry.size_bytes

    def _evict_local_cache(self):
        """Evict items from local cache."""
        # Simple LRU eviction
        if not self.local_cache:
            return

        # Sort by last accessed time
        sorted_items = sorted(
            self.local_cache.items(),
            key=lambda x: x[1].last_accessed or x[1].created_at,
        )

        # Remove oldest items until we have space
        target_size = self.max_local_cache_mb * 1024 * 1024 * 0.8  # 80% of max

        for key, entry in sorted_items:
            if self.local_cache_size <= target_size:
                break

            del self.local_cache[key]
            self.local_cache_size -= entry.size_bytes

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            stats = self.stats.copy()

        # Calculate hit rates
        total_gets = stats["gets"]
        if total_gets > 0:
            stats["local_hit_rate"] = stats["local_hits"] / total_gets
            stats["remote_hit_rate"] = stats["remote_hits"] / total_gets
            stats["miss_rate"] = stats["misses"] / total_gets

        stats["local_cache_entries"] = len(self.local_cache)
        stats["local_cache_size_mb"] = self.local_cache_size / (1024 * 1024)

        return stats

    def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster information."""
        nodes = self.hash_ring.get_all_nodes()

        return {
            "total_nodes": len(nodes),
            "active_nodes": len([n for n in nodes if n.is_active]),
            "replication_factor": self.replication_factor,
            "nodes": [node.to_dict() for node in nodes],
        }


class DistributedCacheManager:
    """High-level manager for distributed caching."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize distributed cache manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.nodes = self._create_nodes_from_config()
        self.client = DistributedCacheClient(
            self.nodes, replication_factor=config.get("replication_factor", 2)
        )

        # Health monitoring
        self.health_check_interval = config.get("health_check_interval", 30)
        self.health_monitor_task = None
        self.is_monitoring = False

    def _create_nodes_from_config(self) -> List[CacheNode]:
        """Create cache nodes from configuration."""
        nodes = []

        for node_config in self.config.get("nodes", []):
            node = CacheNode(
                node_id=node_config["node_id"],
                host=node_config["host"],
                port=node_config["port"],
                capacity_mb=node_config.get("capacity_mb", 1000.0),
            )
            nodes.append(node)

        return nodes

    async def start(self):
        """Start the distributed cache manager."""
        logger.info("Starting distributed cache manager")

        # Start health monitoring
        self.is_monitoring = True
        self.health_monitor_task = asyncio.create_task(self._health_monitor())

    async def stop(self):
        """Stop the distributed cache manager."""
        logger.info("Stopping distributed cache manager")

        self.is_monitoring = False
        if self.health_monitor_task:
            self.health_monitor_task.cancel()
            try:
                await self.health_monitor_task
            except asyncio.CancelledError:
                pass

    async def _health_monitor(self):
        """Monitor health of cache nodes."""
        while self.is_monitoring:
            try:
                await self._check_node_health()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.health_check_interval)

    async def _check_node_health(self):
        """Check health of all nodes."""
        for node in self.nodes:
            try:
                # This would implement actual health check
                # For now, just update heartbeat
                node.last_heartbeat = datetime.now()

                # Check if node is responsive
                # is_healthy = await self._ping_node(node)
                # node.is_active = is_healthy

            except Exception as e:
                logger.error(f"Health check failed for node {node.node_id}: {e}")
                node.is_active = False

    async def get(self, key: str) -> Optional[Any]:
        """Get value from distributed cache."""
        return await self.client.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in distributed cache."""
        return await self.client.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from distributed cache."""
        return await self.client.delete(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        client_stats = self.client.get_stats()
        cluster_info = self.client.get_cluster_info()

        return {
            "client_stats": client_stats,
            "cluster_info": cluster_info,
            "config": {
                "replication_factor": self.config.get("replication_factor", 2),
                "health_check_interval": self.health_check_interval,
            },
        }

    def add_node(self, node_config: Dict[str, Any]):
        """Add a new node to the cluster."""
        node = CacheNode(
            node_id=node_config["node_id"],
            host=node_config["host"],
            port=node_config["port"],
            capacity_mb=node_config.get("capacity_mb", 1000.0),
        )

        self.nodes.append(node)
        self.client.hash_ring.add_node(node)

        logger.info(f"Added node {node.node_id} to cluster")

    def remove_node(self, node_id: str):
        """Remove a node from the cluster."""
        self.nodes = [n for n in self.nodes if n.node_id != node_id]
        self.client.hash_ring.remove_node(node_id)

        logger.info(f"Removed node {node_id} from cluster")


class DistributedDocumentCache:
    """Distributed cache specialized for document processing."""

    def __init__(self, cache_manager: DistributedCacheManager):
        """Initialize distributed document cache.

        Args:
            cache_manager: Distributed cache manager
        """
        self.cache_manager = cache_manager
        self.document_prefix = "doc:"
        self.conversion_prefix = "conv:"
        self.metadata_prefix = "meta:"

    def _make_key(self, prefix: str, doc_id: str, suffix: str = "") -> str:
        """Create cache key with prefix."""
        key = f"{prefix}{doc_id}"
        if suffix:
            key += f":{suffix}"
        return key

    async def get_document(self, doc_id: str) -> Optional[Any]:
        """Get document from cache."""
        key = self._make_key(self.document_prefix, doc_id)
        return await self.cache_manager.get(key)

    async def set_document(self, doc_id: str, document: Any, ttl: int = 3600) -> bool:
        """Set document in cache."""
        key = self._make_key(self.document_prefix, doc_id)
        return await self.cache_manager.set(key, document, ttl)

    async def get_conversion(self, doc_id: str, target_format: str) -> Optional[str]:
        """Get conversion result from cache."""
        key = self._make_key(self.conversion_prefix, doc_id, target_format)
        return await self.cache_manager.get(key)

    async def set_conversion(
        self, doc_id: str, target_format: str, result: str, ttl: int = 3600
    ) -> bool:
        """Set conversion result in cache."""
        key = self._make_key(self.conversion_prefix, doc_id, target_format)
        return await self.cache_manager.set(key, result, ttl)

    async def get_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata from cache."""
        key = self._make_key(self.metadata_prefix, doc_id)
        return await self.cache_manager.get(key)

    async def set_metadata(
        self, doc_id: str, metadata: Dict[str, Any], ttl: int = 7200
    ) -> bool:
        """Set document metadata in cache."""
        key = self._make_key(self.metadata_prefix, doc_id)
        return await self.cache_manager.set(key, metadata, ttl)

    async def invalidate_document(self, doc_id: str) -> bool:
        """Invalidate all cached data for a document."""
        keys = [
            self._make_key(self.document_prefix, doc_id),
            self._make_key(self.metadata_prefix, doc_id),
        ]

        # Also invalidate common conversion formats
        for format_name in ["markdown", "html", "text"]:
            keys.append(self._make_key(self.conversion_prefix, doc_id, format_name))

        # Delete all keys
        results = await asyncio.gather(
            *[self.cache_manager.delete(key) for key in keys], return_exceptions=True
        )

        # Return True if any deletion succeeded
        return any(isinstance(r, bool) and r for r in results)
