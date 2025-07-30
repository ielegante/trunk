"""Tests for cross-document reference system."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from doc_processing.references import (
    AutoRenumberingSystem,
    DependencyVisualizer,
    DocumentAnchor,
    DocumentReference,
    DocumentURI,
    ReferenceScanner,
    URISystem,
)


class TestURISystem(unittest.TestCase):
    """Test URISystem class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.uri_system = URISystem(Path(self.temp_dir))

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_uri_creation(self):
        """Test creating document URIs."""
        # Basic URI
        uri = self.uri_system.create_uri(
            repository="matter-123", document="contract.md"
        )
        self.assertEqual(uri.to_string(), "firm://matter-123/contract.md")

        # URI with sections
        uri = self.uri_system.create_uri(
            repository="matter-123",
            document="contract.md",
            section="payment-terms",
            subsection="late-fees",
        )
        self.assertEqual(
            uri.to_string(), "firm://matter-123/contract.md/payment-terms/late-fees"
        )

        # Template URI
        uri = self.uri_system.create_uri(
            repository="template", document="nda", section="confidentiality"
        )
        self.assertEqual(uri.to_string(), "firm://template/nda/confidentiality")

        # Internal reference
        uri = self.uri_system.create_uri(repository="this-doc", section="section-5")
        self.assertEqual(uri.to_string(), "firm://this-doc/section-5")

    def test_uri_parsing(self):
        """Test parsing URI strings."""
        # Parse basic URI
        uri = self.uri_system.parse_uri("firm://matter-123/contract.md")
        self.assertEqual(uri.repository, "matter-123")
        self.assertEqual(uri.document, "contract.md")

        # Parse complex URI
        uri = self.uri_system.parse_uri(
            "firm://template/nda/confidentiality/exceptions?version=2#para-3"
        )
        self.assertEqual(uri.repository, "template")
        self.assertEqual(uri.document, "nda")
        self.assertEqual(uri.section, "confidentiality")
        self.assertEqual(uri.subsection, "exceptions")
        self.assertEqual(uri.query, {"version": ["2"]})
        self.assertEqual(uri.fragment, "para-3")

        # Parse internal reference
        uri = self.uri_system.parse_uri("firm://this-doc/section-5/subsection-a")
        self.assertTrue(uri.is_internal_reference())
        self.assertEqual(uri.section, "section-5")
        self.assertEqual(uri.subsection, "subsection-a")

    def test_anchor_creation(self):
        """Test creating document anchors."""
        anchor = self.uri_system.create_anchor(
            document_path="matter-123/contract.md",
            anchor_type="section",
            position=100,
            text="2.1 Payment Terms",
        )

        self.assertIsNotNone(anchor.anchor_id)
        self.assertEqual(anchor.document_path, "matter-123/contract.md")
        self.assertEqual(anchor.anchor_type, "section")
        self.assertEqual(anchor.position, 100)

        # Verify anchor is stored
        anchors = self.uri_system.anchors.get("matter-123/contract.md", [])
        self.assertEqual(len(anchors), 1)

    def test_reference_scanning(self):
        """Test scanning for references in content."""
        content = """
        # Contract Agreement

        This agreement references firm://template/nda/confidentiality for terms.

        See Section 5.2 for payment details.

        Related to firm://matter-456/related-doc.md

        The termination clause is in {{termination-clause}}.
        """

        refs = self.uri_system.scan_document_for_references("test.md", content)

        # Should find explicit URI references
        uri_refs = [r for r in refs if r.reference_type == "explicit"]
        self.assertEqual(len(uri_refs), 2)

        # Should find section references
        section_refs = [r for r in refs if r.reference_type == "implicit"]
        self.assertGreater(len(section_refs), 0)

    def test_reference_resolution(self):
        """Test resolving references to anchors."""
        # Create anchor
        anchor = self.uri_system.create_anchor(
            document_path="matter-123/contract.md",
            anchor_type="section",
            position=200,
            text="Payment Terms",
            anchor_id="payment-terms",
        )

        # Create URI pointing to anchor
        uri = self.uri_system.create_uri(
            repository="matter-123", document="contract.md", fragment="payment-terms"
        )

        # Resolve reference
        resolved = self.uri_system.resolve_reference(uri)
        self.assertEqual(resolved.anchor_id, anchor.anchor_id)

    def test_dependency_tracking(self):
        """Test tracking document dependencies."""
        # Create references
        refs = [
            DocumentReference(
                reference_id="ref1",
                source_document="doc1.md",
                source_position=0,
                target_uri=self.uri_system.create_uri(
                    repository="matter", document="doc2.md"
                ),
                reference_text="firm://matter/doc2.md",
                reference_type="explicit",
                created_at=datetime.now(),
                last_verified=datetime.now(),
            ),
            DocumentReference(
                reference_id="ref2",
                source_document="doc1.md",
                source_position=100,
                target_uri=self.uri_system.create_uri(
                    repository="matter", document="doc3.md"
                ),
                reference_text="firm://matter/doc3.md",
                reference_type="explicit",
                created_at=datetime.now(),
                last_verified=datetime.now(),
            ),
        ]

        self.uri_system.references["doc1.md"] = refs

        # Get dependencies
        deps = self.uri_system.get_document_dependencies("doc1.md")
        self.assertEqual(len(deps), 2)
        self.assertIn("firm://matter/doc2.md", deps)
        self.assertIn("firm://matter/doc3.md", deps)


class TestAutoRenumberingSystem(unittest.TestCase):
    """Test AutoRenumberingSystem class."""

    def setUp(self):
        """Set up test fixtures."""
        self.renumber = AutoRenumberingSystem()

    def test_section_parsing(self):
        """Test parsing document structure."""
        content = """# Introduction

This is the introduction.

## Background
### Historical Context

Some background information.

## Methodology

Our approach includes:

### Data Collection
### Analysis

## Results

# Conclusion

Final thoughts.
"""

        sections = self.renumber.parse_document_structure(content)

        # Should have 2 top-level sections
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0].title, "Introduction")
        self.assertEqual(sections[1].title, "Conclusion")

        # Check subsections
        intro_subsections = sections[0].subsections
        self.assertEqual(len(intro_subsections), 3)
        self.assertEqual(intro_subsections[0].title, "Background")
        self.assertEqual(intro_subsections[1].title, "Methodology")
        self.assertEqual(intro_subsections[2].title, "Results")

        # Check sub-subsections
        background_subsections = intro_subsections[0].subsections
        self.assertEqual(len(background_subsections), 1)
        self.assertEqual(background_subsections[0].title, "Historical Context")

    def test_placeholder_extraction(self):
        """Test extracting placeholders from content."""
        content = """
        See {{payment-terms}} for details.

        The {{termination-clause}} applies here.

        Refer to {{confidentiality}} and {{non-compete}}.
        """

        placeholders = self.renumber.extract_placeholders(content)

        self.assertEqual(len(placeholders), 4)
        self.assertIn("payment-terms", placeholders)
        self.assertIn("termination-clause", placeholders)
        self.assertIn("confidentiality", placeholders)
        self.assertIn("non-compete", placeholders)

    def test_renumbering_application(self):
        """Test applying renumbering to content."""
        content = """# Payment Terms

See {{payment-terms}} for payment details.

## Late Fees

Refer to Section 1.1 above.

# Termination

The {{termination}} clause.
"""

        result = self.renumber.apply_renumbering(content)

        # Placeholders should be replaced with section numbers
        self.assertIn("1.", result)  # Payment Terms is section 1
        self.assertIn("2.", result)  # Termination is section 2

        # Section references should be updated
        self.assertNotIn("{{payment-terms}}", result)
        self.assertNotIn("{{termination}}", result)

    def test_custom_numbering_schemes(self):
        """Test custom numbering schemes."""
        from doc_processing.references.auto_renumber import RenumberingRule

        # Add Roman numeral rule
        rule = RenumberingRule(
            rule_id="articles",
            name="Articles",
            pattern=r"^#\s+Article",
            numbering_scheme="roman_upper",
            prefix="Article",
            start_at=1,
        )

        content = """# Article One

First article.

# Article Two

Second article.

# Article Three

Third article.
"""

        result = self.renumber.apply_renumbering(content, [rule])
        sections = self.renumber.parse_document_structure(content)

        # Check Roman numerals
        self.assertEqual(sections[0].number.to_string(), "1.")
        self.assertEqual(sections[1].number.to_string(), "2.")
        self.assertEqual(sections[2].number.to_string(), "3.")


class TestReferenceScanner(unittest.TestCase):
    """Test ReferenceScanner class."""

    def setUp(self):
        """Set up test fixtures."""
        self.scanner = ReferenceScanner()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_change_impact_analysis(self):
        """Test analyzing change impact."""
        old_content = """# Contract Agreement

## Payment Terms

Payment is due within 30 days.

## Termination

Either party may terminate with notice.
"""

        new_content = """# Contract Agreement

## Payment Terms

Payment is due within 60 days.

## Cancellation

Either party may cancel with notice.
"""

        report = self.scanner.analyze_change_impact(
            "contract.md", old_content, new_content
        )

        # Should detect changes
        self.assertGreater(len(report.changes_detected), 0)

        # Should identify affected sections
        change = report.changes_detected[0]
        self.assertIn("Payment Terms", change.sections_affected)
        self.assertIn("Termination", change.sections_affected)  # Deleted
        self.assertIn("Cancellation", change.sections_affected)  # Added

    def test_dependency_graph_building(self):
        """Test building dependency graph."""
        # Create test repository
        repo_path = Path(self.temp_dir)

        # Create test documents
        doc1 = repo_path / "doc1.md"
        doc1.write_text("Reference to firm://matter/doc2.md")

        doc2 = repo_path / "doc2.md"
        doc2.write_text("Reference to firm://matter/doc3.md")

        doc3 = repo_path / "doc3.md"
        doc3.write_text("No references here")

        # Build graph
        graph = self.scanner.build_dependency_graph(repo_path)

        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertIn("statistics", graph)

        # Check statistics
        stats = graph["statistics"]
        self.assertEqual(stats["total_documents"], 3)
        self.assertGreater(stats["total_references"], 0)


class TestDependencyVisualizer(unittest.TestCase):
    """Test DependencyVisualizer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.visualizer = DependencyVisualizer()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test resources."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_circular_dependency_detection(self):
        """Test detecting circular dependencies."""
        # Create circular references
        from doc_processing.references.dependency_visualizer import (
            DependencyEdge,
            DependencyNode,
        )

        # Add nodes
        self.visualizer.nodes = {
            "doc1": DependencyNode("doc1", "doc1.md", "document", "Doc 1"),
            "doc2": DependencyNode("doc2", "doc2.md", "document", "Doc 2"),
            "doc3": DependencyNode("doc3", "doc3.md", "document", "Doc 3"),
        }

        # Add circular edges: doc1 -> doc2 -> doc3 -> doc1
        self.visualizer.edges = {
            "doc1->doc2": DependencyEdge("e1", "doc1", "doc2", "explicit"),
            "doc2->doc3": DependencyEdge("e2", "doc2", "doc3", "explicit"),
            "doc3->doc1": DependencyEdge("e3", "doc3", "doc1", "explicit"),
        }

        # Detect circular dependencies
        self.visualizer._detect_circular_dependencies()

        # Should generate alert
        circular_alerts = [
            a for a in self.visualizer.alerts if a.alert_type == "circular_dependency"
        ]
        self.assertGreater(len(circular_alerts), 0)

    def test_export_formats(self):
        """Test exporting in different formats."""
        # Add some test data
        from doc_processing.references.dependency_visualizer import (
            DependencyEdge,
            DependencyNode,
        )

        self.visualizer.nodes = {
            "doc1": DependencyNode("doc1", "doc1.md", "document", "Document 1"),
            "template1": DependencyNode(
                "template1", "template/nda.md", "template", "NDA Template"
            ),
        }

        self.visualizer.edges = {
            "doc1->template1": DependencyEdge("e1", "doc1", "template1", "explicit", 2)
        }

        # Test JSON export
        json_data = self.visualizer.export_graph_data("json")
        self.assertIn('"nodes"', json_data)
        self.assertIn('"edges"', json_data)

        # Test DOT export
        dot_data = self.visualizer.export_graph_data("dot")
        self.assertIn("digraph", dot_data)
        self.assertIn("doc1", dot_data)
        self.assertIn("template1", dot_data)

        # Test Mermaid export
        mermaid_data = self.visualizer.export_graph_data("mermaid")
        self.assertIn("graph LR", mermaid_data)
        self.assertIn("doc1", mermaid_data)
        self.assertIn("template1", mermaid_data)

    def test_impact_map_generation(self):
        """Test generating document impact map."""
        # Mock URI system with dependencies
        mock_uri_system = Mock()
        mock_uri_system.get_document_dependencies.return_value = {
            "dep1.md": [],
            "dep2.md": [],
        }
        mock_uri_system.get_document_dependents.return_value = {
            "dependent1.md": [],
            "dependent2.md": [],
            "dependent3.md": [],
        }

        self.visualizer.uri_system = mock_uri_system

        # Generate impact map
        impact_map = self.visualizer.get_document_impact_map("test.md")

        self.assertEqual(impact_map["document"], "test.md")
        self.assertIn("impact_levels", impact_map)
        self.assertIn("impact_score", impact_map)
        self.assertIn("risk_level", impact_map)

        # Check impact levels
        levels = impact_map["impact_levels"]
        self.assertEqual(len(levels["direct_dependencies"]), 2)
        self.assertEqual(len(levels["direct_dependents"]), 3)


if __name__ == "__main__":
    unittest.main()
