"""Tests for distributed caching system."""

import asyncio
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from doc_processing.optimization.distributed_cache import (
    CacheEntry,
    CacheNode,
    ConsistentHashRing,
    DistributedCacheClient,
    DistributedCacheManager,
    DistributedDocumentCache,
)


class TestCacheNode:
    """Test cases for CacheNode."""

    def test_cache_node_creation(self):
        """Test cache node creation."""
        node = CacheNode(
            node_id="node1", host="localhost", port=6379, capacity_mb=1000.0
        )

        assert node.node_id == "node1"
        assert node.host == "localhost"
        assert node.port == 6379
        assert node.is_active is True
        assert node.capacity_mb == 1000.0
        assert node.used_mb == 0.0

    def test_cache_node_to_dict(self):
        """Test cache node serialization."""
        node = CacheNode(
            node_id="node1",
            host="localhost",
            port=6379,
            last_heartbeat=datetime(2023, 1, 1, 12, 0, 0),
        )

        data = node.to_dict()

        assert data["node_id"] == "node1"
        assert data["host"] == "localhost"
        assert data["port"] == 6379
        assert data["last_heartbeat"] == "2023-01-01T12:00:00"


class TestCacheEntry:
    """Test cases for CacheEntry."""

    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            size_bytes=100,
            created_at=datetime.now(),
        )

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.size_bytes == 100
        assert entry.access_count == 0
        assert entry.version == 1

    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        # Non-expiring entry
        entry1 = CacheEntry(
            key="test_key",
            value="test_value",
            size_bytes=100,
            created_at=datetime.now(),
        )
        assert not entry1.is_expired()

        # Expired entry
        entry2 = CacheEntry(
            key="test_key",
            value="test_value",
            size_bytes=100,
            created_at=datetime.now(),
            expires_at=datetime.now() - timedelta(seconds=1),
        )
        assert entry2.is_expired()

        # Future expiration
        entry3 = CacheEntry(
            key="test_key",
            value="test_value",
            size_bytes=100,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=60),
        )
        assert not entry3.is_expired()


class TestConsistentHashRing:
    """Test cases for ConsistentHashRing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.nodes = [
            CacheNode("node1", "host1", 6379),
            CacheNode("node2", "host2", 6379),
            CacheNode("node3", "host3", 6379),
        ]
        self.ring = ConsistentHashRing(self.nodes)

    def test_hash_ring_creation(self):
        """Test hash ring creation."""
        assert len(self.ring.nodes) == 3
        assert len(self.ring.ring) == 9  # 3 nodes × 3 replicas

    def test_get_node_for_key(self):
        """Test getting node for a key."""
        node = self.ring.get_node("test_key")
        assert node is not None
        assert node.node_id in ["node1", "node2", "node3"]

    def test_get_multiple_nodes(self):
        """Test getting multiple nodes for replication."""
        nodes = self.ring.get_nodes("test_key", count=2)
        assert len(nodes) <= 2
        assert all(node.is_active for node in nodes)

        # Should return different nodes
        if len(nodes) == 2:
            assert nodes[0].node_id != nodes[1].node_id

    def test_add_remove_node(self):
        """Test adding and removing nodes."""
        # Add node
        new_node = CacheNode("node4", "host4", 6379)
        self.ring.add_node(new_node)

        assert len(self.ring.nodes) == 4
        assert "node4" in self.ring.nodes

        # Remove node
        self.ring.remove_node("node4")

        assert len(self.ring.nodes) == 3
        assert "node4" not in self.ring.nodes

    def test_consistent_hashing(self):
        """Test that keys consistently map to the same node."""
        # Test that same key always maps to same node
        node1 = self.ring.get_node("consistent_key")
        node2 = self.ring.get_node("consistent_key")

        assert node1.node_id == node2.node_id

        # Test that different keys can map to different nodes
        # (This might occasionally fail due to hash collisions, but should usually pass)
        keys = [f"key_{i}" for i in range(100)]
        nodes = [self.ring.get_node(key) for key in keys]
        unique_nodes = set(node.node_id for node in nodes)

        # Should distribute across multiple nodes
        assert len(unique_nodes) > 1


class TestDistributedCacheClient:
    """Test cases for DistributedCacheClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.nodes = [
            CacheNode("node1", "host1", 6379),
            CacheNode("node2", "host2", 6379),
        ]
        self.client = DistributedCacheClient(self.nodes, replication_factor=2)

    @pytest.mark.asyncio
    async def test_get_miss(self):
        """Test cache miss."""
        # Mock the network calls to return None (miss)
        with patch.object(self.client, "_get_from_node", return_value=None):
            result = await self.client.get("missing_key")
            assert result is None
            assert self.client.stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_hit(self):
        """Test cache hit."""
        # Mock the network calls to return a value
        with patch.object(self.client, "_get_from_node", return_value="test_value"):
            result = await self.client.get("test_key")
            assert result == "test_value"
            assert self.client.stats["remote_hits"] == 1

    @pytest.mark.asyncio
    async def test_local_cache_hit(self):
        """Test local cache hit."""
        # Set up local cache
        self.client._cache_locally("test_key", "test_value")

        # Should hit local cache
        result = await self.client.get("test_key")
        assert result == "test_value"
        assert self.client.stats["local_hits"] == 1

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test successful set operation."""
        # Mock the network calls to return success
        with patch.object(self.client, "_set_on_node", return_value=True):
            success = await self.client.set("test_key", "test_value")
            assert success is True
            assert self.client.stats["sets"] == 1

    @pytest.mark.asyncio
    async def test_set_failure(self):
        """Test set operation failure."""
        # Mock the network calls to return failure
        with patch.object(self.client, "_set_on_node", return_value=False):
            success = await self.client.set("test_key", "test_value")
            assert success is False
            assert self.client.stats["sets"] == 1

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful delete operation."""
        # Mock the network calls to return success
        with patch.object(self.client, "_delete_from_node", return_value=True):
            success = await self.client.delete("test_key")
            assert success is True
            assert self.client.stats["deletes"] == 1

    def test_local_cache_eviction(self):
        """Test local cache eviction."""
        # Set a small max cache size
        self.client.max_local_cache_mb = 0.001  # 1KB

        # Add entries that exceed the limit
        for i in range(10):
            key = f"key_{i}"
            value = "x" * 200  # 200 bytes each
            self.client._cache_locally(key, value)

        # Should have evicted some entries
        assert len(self.client.local_cache) < 10
        assert self.client.local_cache_size < 1024  # Less than 1KB

    def test_get_stats(self):
        """Test statistics collection."""
        stats = self.client.get_stats()

        required_keys = [
            "gets",
            "sets",
            "deletes",
            "local_hits",
            "remote_hits",
            "misses",
            "local_cache_entries",
            "local_cache_size_mb",
        ]

        for key in required_keys:
            assert key in stats

    def test_get_cluster_info(self):
        """Test cluster information."""
        info = self.client.get_cluster_info()

        assert info["total_nodes"] == 2
        assert info["active_nodes"] == 2
        assert info["replication_factor"] == 2
        assert len(info["nodes"]) == 2


class TestDistributedCacheManager:
    """Test cases for DistributedCacheManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "nodes": [
                {"node_id": "node1", "host": "host1", "port": 6379},
                {"node_id": "node2", "host": "host2", "port": 6379},
            ],
            "replication_factor": 2,
            "health_check_interval": 1,
        }
        self.manager = DistributedCacheManager(self.config)

    def test_manager_initialization(self):
        """Test manager initialization."""
        assert len(self.manager.nodes) == 2
        assert self.manager.client.replication_factor == 2
        assert self.manager.health_check_interval == 1

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the manager."""
        await self.manager.start()
        assert self.manager.is_monitoring is True
        assert self.manager.health_monitor_task is not None

        await self.manager.stop()
        assert self.manager.is_monitoring is False

    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test cache operations through manager."""
        # Mock the client methods
        with patch.object(self.manager.client, "get", return_value="test_value"):
            result = await self.manager.get("test_key")
            assert result == "test_value"

        with patch.object(self.manager.client, "set", return_value=True):
            success = await self.manager.set("test_key", "test_value")
            assert success is True

        with patch.object(self.manager.client, "delete", return_value=True):
            success = await self.manager.delete("test_key")
            assert success is True

    def test_add_remove_node(self):
        """Test adding and removing nodes."""
        # Add node
        new_node_config = {"node_id": "node3", "host": "host3", "port": 6379}
        self.manager.add_node(new_node_config)

        assert len(self.manager.nodes) == 3
        assert any(node.node_id == "node3" for node in self.manager.nodes)

        # Remove node
        self.manager.remove_node("node3")

        assert len(self.manager.nodes) == 2
        assert not any(node.node_id == "node3" for node in self.manager.nodes)

    def test_get_stats(self):
        """Test getting comprehensive statistics."""
        stats = self.manager.get_stats()

        assert "client_stats" in stats
        assert "cluster_info" in stats
        assert "config" in stats
        assert stats["config"]["replication_factor"] == 2


class TestDistributedDocumentCache:
    """Test cases for DistributedDocumentCache."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a mock cache manager
        self.mock_manager = Mock()
        self.mock_manager.get = AsyncMock()
        self.mock_manager.set = AsyncMock()
        self.mock_manager.delete = AsyncMock()

        self.doc_cache = DistributedDocumentCache(self.mock_manager)

    @pytest.mark.asyncio
    async def test_document_operations(self):
        """Test document cache operations."""
        doc_id = "test_doc_123"
        document = {"title": "Test Document", "content": "Test content"}

        # Test set document
        self.mock_manager.set.return_value = True
        success = await self.doc_cache.set_document(doc_id, document)
        assert success is True

        # Verify the key format
        call_args = self.mock_manager.set.call_args
        assert call_args[0][0] == f"doc:{doc_id}"
        assert call_args[0][1] == document

        # Test get document
        self.mock_manager.get.return_value = document
        result = await self.doc_cache.get_document(doc_id)
        assert result == document

        # Verify the key format
        call_args = self.mock_manager.get.call_args
        assert call_args[0][0] == f"doc:{doc_id}"

    @pytest.mark.asyncio
    async def test_conversion_operations(self):
        """Test conversion cache operations."""
        doc_id = "test_doc_123"
        target_format = "markdown"
        conversion_result = "# Test Document\n\nTest content"

        # Test set conversion
        self.mock_manager.set.return_value = True
        success = await self.doc_cache.set_conversion(
            doc_id, target_format, conversion_result
        )
        assert success is True

        # Verify the key format
        call_args = self.mock_manager.set.call_args
        assert call_args[0][0] == f"conv:{doc_id}:{target_format}"
        assert call_args[0][1] == conversion_result

        # Test get conversion
        self.mock_manager.get.return_value = conversion_result
        result = await self.doc_cache.get_conversion(doc_id, target_format)
        assert result == conversion_result

    @pytest.mark.asyncio
    async def test_metadata_operations(self):
        """Test metadata cache operations."""
        doc_id = "test_doc_123"
        metadata = {"pages": 5, "author": "Test Author"}

        # Test set metadata
        self.mock_manager.set.return_value = True
        success = await self.doc_cache.set_metadata(doc_id, metadata)
        assert success is True

        # Verify the key format
        call_args = self.mock_manager.set.call_args
        assert call_args[0][0] == f"meta:{doc_id}"
        assert call_args[0][1] == metadata

        # Test get metadata
        self.mock_manager.get.return_value = metadata
        result = await self.doc_cache.get_metadata(doc_id)
        assert result == metadata

    @pytest.mark.asyncio
    async def test_document_invalidation(self):
        """Test document invalidation."""
        doc_id = "test_doc_123"

        # Mock successful deletions
        self.mock_manager.delete.return_value = True

        success = await self.doc_cache.invalidate_document(doc_id)
        assert success is True

        # Should have called delete multiple times
        assert (
            self.mock_manager.delete.call_count >= 3
        )  # doc, meta, and conversion keys

        # Verify some of the expected keys were deleted
        call_args_list = [
            call[0][0] for call in self.mock_manager.delete.call_args_list
        ]
        assert f"doc:{doc_id}" in call_args_list
        assert f"meta:{doc_id}" in call_args_list


class TestDistributedCacheIntegration:
    """Integration tests for distributed cache system."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete distributed cache workflow."""
        # Set up configuration
        config = {
            "nodes": [
                {"node_id": "node1", "host": "localhost", "port": 6379},
                {"node_id": "node2", "host": "localhost", "port": 6380},
            ],
            "replication_factor": 2,
            "health_check_interval": 5,
        }

        # Create manager
        manager = DistributedCacheManager(config)
        doc_cache = DistributedDocumentCache(manager)

        # Mock the network operations
        with (
            patch.object(manager.client, "_get_from_node", return_value=None),
            patch.object(manager.client, "_set_on_node", return_value=True),
            patch.object(manager.client, "_delete_from_node", return_value=True),
        ):
            # Test document workflow
            doc_id = "integration_test_doc"
            document = {"title": "Integration Test", "content": "Test content"}

            # Set document
            success = await doc_cache.set_document(doc_id, document)
            assert success is True

            # Set conversion
            conversion = "# Integration Test\n\nTest content"
            success = await doc_cache.set_conversion(doc_id, "markdown", conversion)
            assert success is True

            # Set metadata
            metadata = {"pages": 1, "words": 3}
            success = await doc_cache.set_metadata(doc_id, metadata)
            assert success is True

            # Get statistics
            stats = manager.get_stats()
            assert stats["client_stats"]["sets"] == 3

            # Invalidate document
            success = await doc_cache.invalidate_document(doc_id)
            assert success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
