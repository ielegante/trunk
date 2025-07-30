"""Tests for Sprint 8 advanced features."""

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from doc_processing.bulk import BulkOperation, BulkOperationsManager, FolderStructure
from doc_processing.locking import (
    DocumentLock,
    DocumentLockingSystem,
    LockCoordinator,
    LockNotification,
    LockRequest,
)
from doc_processing.pdf import PDFDocument, PDFTextExtractor, PDFTracker


class TestDocumentLocking(unittest.TestCase):
    """Test document locking system."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        self.locking_system = DocumentLockingSystem(self.repo_path)

        # Create test document
        self.test_doc = self.repo_path / "test.md"
        self.test_doc.write_text("# Test Document")

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    async def test_acquire_lock(self):
        """Test acquiring a document lock."""
        request = LockRequest(
            document_path="test.md",
            requested_by="user@example.com",
            duration_minutes=30,
            reason="Editing document",
        )

        success, lock, message = await self.locking_system.acquire_lock(request)

        self.assertTrue(success)
        self.assertIsNotNone(lock)
        self.assertEqual(lock.locked_by, "user@example.com")
        self.assertEqual(lock.document_path, "test.md")
        self.assertIn("success", message.lower())

    async def test_lock_conflict(self):
        """Test lock conflict handling."""
        # First user locks document
        request1 = LockRequest(
            document_path="test.md",
            requested_by="user1@example.com",
            duration_minutes=30,
        )

        success1, lock1, _ = await self.locking_system.acquire_lock(request1)
        self.assertTrue(success1)

        # Second user tries to lock
        request2 = LockRequest(
            document_path="test.md",
            requested_by="user2@example.com",
            duration_minutes=30,
        )

        success2, lock2, message = await self.locking_system.acquire_lock(request2)

        self.assertFalse(success2)
        self.assertIsNone(lock2)
        self.assertIn("locked by user1", message)

    async def test_force_lock(self):
        """Test force lock acquisition."""
        # First user locks document
        request1 = LockRequest(
            document_path="test.md",
            requested_by="user1@example.com",
            duration_minutes=30,
        )

        await self.locking_system.acquire_lock(request1)

        # Admin force locks
        request2 = LockRequest(
            document_path="test.md",
            requested_by="admin@example.com",
            duration_minutes=30,
            force=True,
        )

        success, lock, message = await self.locking_system.acquire_lock(request2)

        self.assertTrue(success)
        self.assertEqual(lock.locked_by, "admin@example.com")

    async def test_lock_expiration(self):
        """Test lock expiration."""
        # Create expired lock
        lock = DocumentLock(
            lock_id="test-lock",
            document_path="test.md",
            locked_by="user@example.com",
            locked_at=datetime.now() - timedelta(hours=2),
            expires_at=datetime.now() - timedelta(hours=1),
            lock_type="exclusive",
        )

        self.locking_system.active_locks["test.md"] = lock

        # Try to get lock - should be None (expired)
        retrieved_lock = self.locking_system.get_lock("test.md")
        self.assertIsNone(retrieved_lock)

        # Should be able to acquire new lock
        request = LockRequest(
            document_path="test.md", requested_by="newuser@example.com"
        )

        success, new_lock, _ = await self.locking_system.acquire_lock(request)
        self.assertTrue(success)
        self.assertEqual(new_lock.locked_by, "newuser@example.com")

    async def test_extend_lock(self):
        """Test extending a lock."""
        # Acquire lock
        request = LockRequest(
            document_path="test.md",
            requested_by="user@example.com",
            duration_minutes=30,
        )

        success, lock, _ = await self.locking_system.acquire_lock(request)
        original_expiry = lock.expires_at

        # Extend lock
        success, extended_lock, message = await self.locking_system.extend_lock(
            "test.md", "user@example.com", additional_minutes=30
        )

        self.assertTrue(success)
        self.assertGreater(extended_lock.expires_at, original_expiry)
        self.assertIn("extended", message.lower())

    async def test_bulk_lock(self):
        """Test locking multiple documents."""
        # Create test documents
        docs = ["doc1.md", "doc2.md", "doc3.md"]
        for doc in docs:
            (self.repo_path / doc).write_text(f"# {doc}")

        results = await self.locking_system.bulk_lock(
            docs, "user@example.com", duration_minutes=30, reason="Bulk edit"
        )

        self.assertEqual(len(results), 3)
        for doc, (success, message) in results.items():
            self.assertTrue(success)
            self.assertIn("success", message.lower())

    async def test_lock_history(self):
        """Test lock event history."""
        # Perform lock operations
        request = LockRequest(document_path="test.md", requested_by="user@example.com")

        await self.locking_system.acquire_lock(request)
        await self.locking_system.release_lock("test.md", "user@example.com")

        # Check history
        history = self.locking_system.get_lock_history(document_path="test.md")

        self.assertGreater(len(history), 0)
        event_types = [e.event_type for e in history]
        self.assertIn("locked", event_types)
        self.assertIn("unlocked", event_types)


class TestLockCoordinator(unittest.TestCase):
    """Test lock coordination features."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        self.locking_system = DocumentLockingSystem(self.repo_path)
        self.coordinator = LockCoordinator(self.locking_system)

        # Create test document
        self.test_doc = self.repo_path / "test.md"
        self.test_doc.write_text("# Test Document")

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    async def test_request_lock_with_wait(self):
        """Test waiting for lock availability."""

        # Mock the locking system to simulate delayed availability
        async def mock_acquire(request):
            if not hasattr(mock_acquire, "call_count"):
                mock_acquire.call_count = 0
            mock_acquire.call_count += 1

            if mock_acquire.call_count < 3:
                return False, None, "Document locked"
            else:
                return (
                    True,
                    DocumentLock(
                        lock_id="test",
                        document_path=request.document_path,
                        locked_by=request.requested_by,
                        locked_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(minutes=30),
                        lock_type="exclusive",
                    ),
                    "Lock acquired",
                )

        self.locking_system.acquire_lock = mock_acquire

        request = LockRequest(document_path="test.md", requested_by="user@example.com")

        success, lock, message = await self.coordinator.request_lock_with_wait(
            request, max_wait_minutes=1
        )

        self.assertTrue(success)
        self.assertIsNotNone(lock)

    async def test_coordinate_bulk_operation(self):
        """Test coordinating bulk operations with locks."""
        # Create test documents
        docs = ["doc1.md", "doc2.md"]
        for doc in docs:
            (self.repo_path / doc).write_text(f"# {doc}")

        # Define operation
        async def test_operation(doc_paths):
            return {"processed": doc_paths}

        success, result, message = await self.coordinator.coordinate_bulk_operation(
            docs, "user@example.com", test_operation, lock_duration=30
        )

        self.assertTrue(success)
        self.assertEqual(result["processed"], docs)
        self.assertIn("success", message.lower())

    async def test_lock_recommendations(self):
        """Test lock recommendation system."""
        # Create some locks
        request1 = LockRequest(
            document_path="test.md",
            requested_by="user@example.com",
            duration_minutes=5,  # Expiring soon
        )

        await self.locking_system.acquire_lock(request1)

        recommendations = await self.coordinator.get_lock_recommendations(
            "user@example.com"
        )

        self.assertGreater(len(recommendations), 0)
        rec_types = [r["type"] for r in recommendations]
        self.assertIn("expiring_soon", rec_types)

    async def test_notification_system(self):
        """Test lock notification callbacks."""
        notifications = []

        def notification_callback(notification: LockNotification):
            notifications.append(notification)

        self.coordinator.register_notification_callback(notification_callback)

        # Trigger notification
        request = LockRequest(document_path="test.md", requested_by="user@example.com")

        await self.coordinator.request_lock_with_wait(request)

        self.assertGreater(len(notifications), 0)
        self.assertEqual(notifications[0].event_type, "lock_acquired")


class TestPDFExtraction(unittest.TestCase):
    """Test PDF extraction features."""

    def setUp(self):
        """Set up test fixtures."""
        self.extractor = PDFTextExtractor()
        self.temp_dir = tempfile.mkdtemp()

        # Create test PDF file (mock)
        self.test_pdf = Path(self.temp_dir) / "test.pd"
        self.test_pdf.write_bytes(b"%PDF-1.4\ntest content")

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_extract_metadata(self):
        """Test PDF metadata extraction."""
        # Mock pdfinfo command
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = """Title:          Test Document
Author:         John Doe
Subject:        Legal Contract
Creator:        Microsoft Word
Producer:       Adobe PDF
Pages:          10
Encrypted:      no
CreationDate:   D:20240101120000
ModDate:        D:20240115150000"""

            metadata = self.extractor._extract_metadata(self.test_pdf)

            self.assertEqual(metadata.title, "Test Document")
            self.assertEqual(metadata.author, "John Doe")
            self.assertEqual(metadata.pages, 10)
            self.assertFalse(metadata.encrypted)

    def test_extract_tracking_info(self):
        """Test extraction for tracking purposes."""
        # Mock extraction result
        with patch.object(self.extractor, "extract_text") as mock_extract:
            mock_extract.return_value.success = True
            mock_extract.return_value.full_text = """
                AGREEMENT between ABC Corp and XYZ Inc.

                Section 1. Definitions
                "Agreement" means this contract.

                Section 2. Terms
                This agreement is effective January 1, 2024.

                ___________________________
                Signature
            """
            mock_extract.return_value.metadata.pages = 5
            mock_extract.return_value.pages = [Mock() for _ in range(5)]

            tracking_info = self.extractor.extract_for_tracking(self.test_pdf)

            self.assertTrue(tracking_info["trackable"])
            self.assertEqual(tracking_info["structure"]["total_pages"], 5)
            self.assertGreater(tracking_info["structure"]["sections"], 0)
            self.assertTrue(tracking_info["structure"]["has_signatures"])
            self.assertIn("ABC Corp", tracking_info["content_summary"]["parties"])

    def test_legal_pattern_extraction(self):
        """Test extraction of legal document patterns."""
        text = """
        AGREEMENT

        This Agreement is entered into between ABC Corporation ("Company")
        and John Doe ("Employee") on January 15, 2024.

        Article I - Employment Terms

        Section 1.1 Position
        Employee shall serve as Senior Developer.

        Section 1.2 Compensation
        Base salary of $100,000 per year.

        "Confidential Information" means any proprietary data.

        By: _______________________
        """

        # Test section extraction
        sections = self.extractor._extract_sections(text)
        self.assertGreater(len(sections), 0)

        # Test party extraction
        parties = self.extractor._extract_parties(text)
        # Party extraction includes the ("Company") part
        self.assertTrue(any("ABC Corporation" in party for party in parties))

        # Test definition extraction
        definitions = self.extractor._extract_definitions(text)
        self.assertIn("Confidential Information", definitions)

        # Test date extraction
        dates = self.extractor._extract_dates(text)
        self.assertIn("January 15, 2024", dates)

        # Test signature detection
        has_sigs = self.extractor._has_signatures(text)
        self.assertTrue(has_sigs)


class TestPDFTracker(unittest.TestCase):
    """Test PDF tracking system."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        self.tracker = PDFTracker(self.repo_path)

        # Create test PDFs
        self.test_pdf1 = self.repo_path / "contracts" / "test1.pd"
        self.test_pdf1.parent.mkdir(parents=True)
        self.test_pdf1.write_bytes(b"%PDF-1.4\ntest1")

        self.test_pdf2 = self.repo_path / "docs" / "test2.pd"
        self.test_pdf2.parent.mkdir(parents=True)
        self.test_pdf2.write_bytes(b"%PDF-1.4\ntest2")

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_track_pdf(self):
        """Test tracking a PDF document."""
        # Mock extractor
        with patch.object(
            self.tracker.extractor, "extract_for_tracking"
        ) as mock_extract:
            mock_extract.return_value = {
                "trackable": True,
                "metadata": {"pages": 5},
                "structure": {"total_pages": 5},
            }

            success, doc, message = self.tracker.track_pdf(
                self.test_pdf1, tags=["contract", "legal"]
            )

            self.assertTrue(success)
            self.assertIsNotNone(doc)
            self.assertEqual(doc.file_path, "contracts/test1.pd")
            self.assertIn("contract", doc.tags)

    def test_verify_pdfs(self):
        """Test PDF verification."""
        # Track PDFs first
        with patch.object(
            self.tracker.extractor, "extract_for_tracking"
        ) as mock_extract:
            mock_extract.return_value = {"trackable": True, "metadata": {}}

            self.tracker.track_pdf(self.test_pdf1)
            self.tracker.track_pdf(self.test_pdf2)

        # Verify all
        results = self.tracker.verify_all_pdfs()

        self.assertEqual(len(results["active"]), 2)
        self.assertEqual(len(results["modified"]), 0)
        self.assertEqual(len(results["missing"]), 0)

        # Modify a PDF
        self.test_pdf1.write_bytes(b"%PDF-1.4\nmodified content")

        # Verify again
        results = self.tracker.verify_all_pdfs()

        self.assertEqual(len(results["active"]), 1)
        self.assertEqual(len(results["modified"]), 1)

    def test_bulk_track(self):
        """Test bulk PDF tracking."""
        with patch.object(
            self.tracker.extractor, "extract_for_tracking"
        ) as mock_extract:
            mock_extract.return_value = {"trackable": True, "metadata": {}}

            results = self.tracker.bulk_track(tags=["bulk"])

            self.assertEqual(results["total"], 2)
            self.assertEqual(results["tracked"], 2)
            self.assertEqual(results["failed"], 0)

    def test_search_pdfs(self):
        """Test PDF search functionality."""
        # Track PDFs with different metadata
        with patch.object(
            self.tracker.extractor, "extract_for_tracking"
        ) as mock_extract:
            mock_extract.return_value = {"trackable": True, "metadata": {}}

            self.tracker.track_pdf(self.test_pdf1, tags=["contract"])
            self.tracker.track_pdf(self.test_pdf2, tags=["memo"])

        # Search by tag
        results = self.tracker.search_pdfs(tags=["contract"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_path, "contracts/test1.pd")

        # Search by path
        results = self.tracker.search_pdfs(query="contracts")
        self.assertEqual(len(results), 1)


class TestBulkOperations(unittest.TestCase):
    """Test bulk operations manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        self.source_dir = Path(self.temp_dir) / "source"
        self.source_dir.mkdir()

        self.bulk_manager = BulkOperationsManager(self.repo_path)

        # Create test files
        self._create_test_structure()

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_test_structure(self):
        """Create test file structure."""
        # Create folders
        (self.source_dir / "contracts").mkdir()
        (self.source_dir / "memos").mkdir()

        # Create files
        (self.source_dir / "contracts" / "contract1.docx").write_text("Contract 1")
        (self.source_dir / "contracts" / "contract2.pd").write_bytes(b"PDF content")
        (self.source_dir / "memos" / "memo1.md").write_text("# Memo 1")
        (self.source_dir / "readme.txt").write_text("README")

    async def test_import_folder_structure(self):
        """Test importing folder structure."""
        result = await self.bulk_manager.import_folder_structure(
            self.source_dir,
            self.repo_path / "imported",
            options={"preserve_structure": True},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.total_items, 4)
        self.assertEqual(result.processed_items, 4)

        # Check preserved structure
        imported_contract = self.repo_path / "imported" / "contracts" / "contract1.docx"
        self.assertTrue(imported_contract.exists())

    def test_analyze_folder_structure(self):
        """Test folder structure analysis."""
        structure = self.bulk_manager.analyze_folder_structure(self.source_dir)

        self.assertEqual(structure.total_files, 4)
        self.assertEqual(structure.total_folders, 2)
        self.assertIn("word", structure.file_types)
        self.assertIn("pd", structure.file_types)
        self.assertIn("markdown", structure.file_types)

    async def test_organize_documents(self):
        """Test document organization."""
        # Copy files to repo
        import shutil

        shutil.copytree(self.source_dir, self.repo_path / "to_organize")

        result = await self.bulk_manager.organize_documents(
            self.repo_path / "to_organize", organization_scheme="by_type"
        )

        self.assertTrue(result.success)
        self.assertEqual(result.processed_items, 4)

        # Check organization
        self.assertTrue((self.repo_path / "to_organize" / "word").exists())
        self.assertTrue((self.repo_path / "to_organize" / "pd").exists())
        self.assertTrue((self.repo_path / "to_organize" / "markdown").exists())

    async def test_parallel_processing(self):
        """Test parallel processing capabilities."""
        items = list(range(10))

        async def process_item(item):
            await asyncio.sleep(0.1)  # Simulate work
            return item * 2

        results = await self.bulk_manager.parallel_process(
            items, process_item, max_workers=4
        )

        self.assertEqual(len(results), 10)
        self.assertEqual(results[0], 0)
        self.assertEqual(results[5], 10)


if __name__ == "__main__":
    # Run async tests
    import asyncio

    def run_async_test(test_func):
        """Helper to run async test methods."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test_func())
        finally:
            loop.close()

    # Patch unittest to handle async tests
    original_run = unittest.TestCase.run

    def async_test_run(self, result=None):
        test_method = getattr(self, self._testMethodName)
        if asyncio.iscoroutinefunction(test_method):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(test_method())
            finally:
                loop.close()
        else:
            original_run(self, result)

    unittest.TestCase.run = async_test_run

    unittest.main()
