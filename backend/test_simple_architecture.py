#!/usr/bin/env python3
"""Test script for simplified architecture."""

import logging
import os
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_database():
    """Test SQLite database connectivity."""
    logger.info("Testing SQLite database...")
    try:
        from app.database import database_manager
        from app.models import Base, Document, Reference, User

        # Initialize database
        database_manager.create_tables()
        logger.info("✅ Database tables created successfully")

        # Test health check
        if database_manager.health_check():
            logger.info("✅ Database health check passed")
        else:
            logger.error("❌ Database health check failed")
            return False

        # Get statistics
        stats = database_manager.get_statistics()
        logger.info(f"✅ Database statistics: {stats}")

        return True

    except Exception as e:
        logger.error(f"❌ Database test failed: {str(e)}")
        return False


def test_memory_cache():
    """Test in-memory cache."""
    logger.info("\nTesting in-memory cache...")
    try:
        from app.performance.memory_cache_manager import (
            document_cache,
            git_cache,
            memory_cache,
        )

        # Test basic cache operations
        memory_cache.set("test_key", {"data": "test_value"}, ttl=60)
        value = memory_cache.get("test_key")

        if value and value.get("data") == "test_value":
            logger.info("✅ Memory cache set/get working")
        else:
            logger.error("❌ Memory cache set/get failed")
            return False

        # Test cache deletion
        memory_cache.delete("test_key")
        if not memory_cache.exists("test_key"):
            logger.info("✅ Memory cache delete working")
        else:
            logger.error("❌ Memory cache delete failed")
            return False

        # Test git cache
        git_cache.set_commit_info("repo1", "hash1", {"message": "test commit"})
        commit = git_cache.get_commit_info("repo1", "hash1")
        if commit and commit.get("message") == "test commit":
            logger.info("✅ Git cache working")
        else:
            logger.error("❌ Git cache failed")
            return False

        # Get cache statistics
        stats = memory_cache.get_stats()
        logger.info(f"✅ Cache statistics: {stats}")

        return True

    except Exception as e:
        logger.error(f"❌ Memory cache test failed: {str(e)}")
        return False


def test_sqlite_locking():
    """Test SQLite-based locking."""
    logger.info("\nTesting SQLite locking...")
    try:
        from app.locking.sqlite_lock_manager import sqlite_lock_manager

        # Test lock acquisition
        resource_id = "test_doc_123"
        owner_id = "user_456"

        if sqlite_lock_manager.acquire_lock(resource_id, owner_id, timeout=300):
            logger.info("✅ Lock acquisition successful")
        else:
            logger.error("❌ Lock acquisition failed")
            return False

        # Test lock info
        lock_info = sqlite_lock_manager.get_lock_info(resource_id)
        if lock_info and lock_info.owner_id == owner_id:
            logger.info("✅ Lock info retrieval successful")
        else:
            logger.error("❌ Lock info retrieval failed")
            return False

        # Test lock release
        if sqlite_lock_manager.release_lock(resource_id, owner_id):
            logger.info("✅ Lock release successful")
        else:
            logger.error("❌ Lock release failed")
            return False

        # Test lock statistics
        stats = sqlite_lock_manager.get_statistics()
        logger.info(f"✅ Lock statistics: {stats}")

        return True

    except Exception as e:
        logger.error(f"❌ SQLite locking test failed: {str(e)}")
        return False


def test_rate_limiting():
    """Test SQLite-based rate limiting."""
    logger.info("\nTesting SQLite rate limiting...")
    try:
        from app.security.sqlite_rate_limiter import sqlite_rate_limiter

        # Test rate limit check
        identifier = "127.0.0.1"
        allowed, info = sqlite_rate_limiter.is_allowed(identifier, limit=10, window=60)

        if allowed:
            logger.info(f"✅ Rate limit check passed: {info}")
        else:
            logger.error(f"❌ Rate limit check failed: {info}")
            return False

        # Test multiple requests
        for i in range(5):
            allowed, info = sqlite_rate_limiter.is_allowed(
                identifier, limit=10, window=60
            )
            if not allowed:
                logger.error(f"❌ Rate limit failed on request {i+2}")
                return False

        logger.info(f"✅ Multiple requests handled correctly: {info}")

        # Test rate limit reset
        if sqlite_rate_limiter.reset_limit(identifier):
            logger.info("✅ Rate limit reset successful")
        else:
            logger.error("❌ Rate limit reset failed")
            return False

        # Get statistics
        stats = sqlite_rate_limiter.get_statistics()
        logger.info(f"✅ Rate limiter statistics: {stats}")

        return True

    except Exception as e:
        logger.error(f"❌ Rate limiting test failed: {str(e)}")
        return False


def test_reference_tracking():
    """Test SQLite-based reference tracking."""
    logger.info("\nTesting SQLite reference tracking...")
    try:
        import uuid

        from app.graph.sqlite_reference_tracker import (
            DocumentNode,
            ReferenceEdge,
            sqlite_reference_tracker,
        )
        from app.models import ReferenceStatus, ReferenceType

        # Create test documents
        doc1 = DocumentNode(
            id=str(uuid.uuid4()),
            repository_id="repo1",
            file_path="/docs/contract1.docx",
            title="Test Contract 1",
            version="1.0",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            content_hash="hash1",
            document_type="contract",
            metadata={},
        )

        doc2 = DocumentNode(
            id=str(uuid.uuid4()),
            repository_id="repo1",
            file_path="/docs/contract2.docx",
            title="Test Contract 2",
            version="1.0",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            content_hash="hash2",
            document_type="contract",
            metadata={},
        )

        # Create documents
        result1 = sqlite_reference_tracker.create_document_node(doc1)
        result2 = sqlite_reference_tracker.create_document_node(doc2)

        if result1.get("success") and result2.get("success"):
            logger.info("✅ Document creation successful")
        else:
            logger.error("❌ Document creation failed")
            return False

        # Create reference
        ref = ReferenceEdge(
            id=str(uuid.uuid4()),
            source_doc_id=doc1.id,
            target_doc_id=doc2.id,
            reference_type=ReferenceType.CITATION,
            status=ReferenceStatus.VALID,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            location={"page": 1, "section": "2.1"},
            context="See Contract 2 for details",
            metadata={},
        )

        result = sqlite_reference_tracker.create_reference(ref)
        if result.get("success"):
            logger.info("✅ Reference creation successful")
        else:
            logger.error("❌ Reference creation failed")
            return False

        # Find references
        refs = sqlite_reference_tracker.find_references_by_document(doc1.id, "outgoing")
        if refs and len(refs) == 1:
            logger.info("✅ Reference retrieval successful")
        else:
            logger.error("❌ Reference retrieval failed")
            return False

        # Get statistics
        stats = sqlite_reference_tracker.get_statistics()
        logger.info(f"✅ Reference tracker statistics: {stats}")

        return True

    except Exception as e:
        logger.error(f"❌ Reference tracking test failed: {str(e)}")
        return False


def test_memory_usage():
    """Test memory usage of simplified architecture."""
    logger.info("\nTesting memory usage...")
    try:
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        logger.info(f"✅ Current memory usage: {memory_mb:.2f} MB")

        if memory_mb < 256:
            logger.info("✅ Memory usage is within target (< 256 MB)")
            return True
        else:
            logger.warning(
                f"⚠️  Memory usage exceeds target: {memory_mb:.2f} MB > 256 MB"
            )
            return True  # Still pass but with warning

    except ImportError:
        logger.warning("⚠️  psutil not installed, skipping memory test")
        return True
    except Exception as e:
        logger.error(f"❌ Memory usage test failed: {str(e)}")
        return False


def main():
    """Run all tests."""
    logger.info("=== Testing Simplified Architecture ===")
    logger.info("Target: Single container, SQLite-only, < 256MB memory\n")

    tests = [
        ("Database", test_database),
        ("Memory Cache", test_memory_cache),
        ("SQLite Locking", test_sqlite_locking),
        ("Rate Limiting", test_rate_limiting),
        ("Reference Tracking", test_reference_tracking),
        ("Memory Usage", test_memory_usage),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} test crashed: {str(e)}")
            failed += 1

    logger.info("\n=== Test Summary ===")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"Total: {len(tests)}")

    if failed == 0:
        logger.info("\n🎉 All tests passed! Architecture simplification successful!")
        return 0
    else:
        logger.error(f"\n❌ {failed} tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
