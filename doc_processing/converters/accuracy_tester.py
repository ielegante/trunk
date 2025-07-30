"""Round-trip accuracy testing and validation system for document conversion."""

import hashlib
import json
import logging
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .diff_visualizer import DocumentDiffVisualizer
from .google_docs import ConversionResult, GoogleDocsConverter

logger = logging.getLogger(__name__)


@dataclass
class AccuracyTestResult:
    """Result of an accuracy test."""

    test_id: str
    document_id: str
    test_type: str  # 'round_trip', 'content_preservation', 'formatting_preservation'
    passed: bool
    accuracy_score: float
    metrics: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    execution_time: float
    test_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "test_id": self.test_id,
            "document_id": self.document_id,
            "test_type": self.test_type,
            "passed": self.passed,
            "accuracy_score": self.accuracy_score,
            "metrics": self.metrics,
            "errors": self.errors,
            "warnings": self.warnings,
            "execution_time": self.execution_time,
            "test_timestamp": self.test_timestamp,
        }


@dataclass
class TestSuite:
    """Collection of accuracy tests."""

    name: str
    description: str
    tests: List[AccuracyTestResult]
    overall_score: float
    pass_rate: float
    execution_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "tests": [test.to_dict() for test in self.tests],
            "overall_score": self.overall_score,
            "pass_rate": self.pass_rate,
            "execution_time": self.execution_time,
        }


class AccuracyTester:
    """Tests round-trip accuracy of document conversion."""

    def __init__(
        self,
        converter: GoogleDocsConverter,
        diff_visualizer: Optional[DocumentDiffVisualizer] = None,
    ):
        """Initialize accuracy tester.

        Args:
            converter: GoogleDocsConverter instance
            diff_visualizer: Optional DocumentDiffVisualizer instance
        """
        self.converter = converter
        self.diff_visualizer = diff_visualizer or DocumentDiffVisualizer()
        self.test_results: List[AccuracyTestResult] = []

        # Test configuration
        self.accuracy_threshold = 0.95
        self.content_similarity_threshold = 0.90
        self.formatting_preservation_threshold = 0.85
        self.max_test_time = 300  # 5 minutes

    def test_round_trip_accuracy(self, document_id: str) -> AccuracyTestResult:
        """Test round-trip conversion accuracy.

        Args:
            document_id: Google Docs document ID

        Returns:
            AccuracyTestResult with test results
        """
        test_id = f"round_trip_{document_id}_{int(time.time())}"
        start_time = time.time()
        errors = []
        warnings = []
        metrics = {}

        try:
            # Step 1: Convert Google Docs to Markdown
            logger.info(f"Starting round-trip test for document {document_id}")

            original_conversion = self.converter.to_markdown(document_id)
            original_markdown = original_conversion.content

            # Step 2: Convert Markdown back to Google Docs
            reconverted_doc_id = self.converter.from_markdown(original_markdown)

            # Step 3: Convert the reconverted document back to Markdown
            reconverted_conversion = self.converter.to_markdown(reconverted_doc_id)
            reconverted_markdown = reconverted_conversion.content

            # Step 4: Compare original and reconverted Markdown
            accuracy_metrics = self._compare_conversions(
                original_conversion,
                reconverted_conversion,
                original_markdown,
                reconverted_markdown,
            )

            # Step 5: Calculate overall accuracy score
            overall_score = self._calculate_overall_accuracy(accuracy_metrics)

            # Update metrics
            metrics.update(accuracy_metrics)
            metrics["overall_score"] = overall_score

            # Determine if test passed
            passed = overall_score >= self.accuracy_threshold

            if not passed:
                errors.append(
                    f"Accuracy score {overall_score:.3f} below threshold {self.accuracy_threshold}"
                )

            # Clean up temporary document
            try:
                # Note: In practice, you'd want to delete the temporary document
                # For now, we'll just log it
                logger.debug(f"Temporary document created: {reconverted_doc_id}")
            except Exception as e:
                warnings.append(f"Failed to clean up temporary document: {e}")

        except Exception as e:
            logger.error(f"Round-trip test failed for document {document_id}: {e}")
            errors.append(str(e))
            overall_score = 0.0
            passed = False

        execution_time = time.time() - start_time

        result = AccuracyTestResult(
            test_id=test_id,
            document_id=document_id,
            test_type="round_trip",
            passed=passed,
            accuracy_score=overall_score,
            metrics=metrics,
            errors=errors,
            warnings=warnings,
            execution_time=execution_time,
            test_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        self.test_results.append(result)
        return result

    def test_content_preservation(self, document_id: str) -> AccuracyTestResult:
        """Test content preservation during conversion.

        Args:
            document_id: Google Docs document ID

        Returns:
            AccuracyTestResult with content preservation test results
        """
        test_id = f"content_preservation_{document_id}_{int(time.time())}"
        start_time = time.time()
        errors = []
        warnings = []
        metrics = {}

        try:
            # Convert document to Markdown
            conversion_result = self.converter.to_markdown(document_id)

            # Extract content metrics
            content_metrics = self._analyze_content_preservation(conversion_result)

            # Calculate content preservation score
            content_score = self._calculate_content_preservation_score(content_metrics)

            metrics.update(content_metrics)
            metrics["content_score"] = content_score

            # Determine if test passed
            passed = content_score >= self.content_similarity_threshold

            if not passed:
                errors.append(
                    f"Content preservation score {content_score:.3f} below threshold {self.content_similarity_threshold}"
                )

        except Exception as e:
            logger.error(
                f"Content preservation test failed for document {document_id}: {e}"
            )
            errors.append(str(e))
            content_score = 0.0
            passed = False

        execution_time = time.time() - start_time

        result = AccuracyTestResult(
            test_id=test_id,
            document_id=document_id,
            test_type="content_preservation",
            passed=passed,
            accuracy_score=content_score,
            metrics=metrics,
            errors=errors,
            warnings=warnings,
            execution_time=execution_time,
            test_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        self.test_results.append(result)
        return result

    def test_formatting_preservation(self, document_id: str) -> AccuracyTestResult:
        """Test formatting preservation during conversion.

        Args:
            document_id: Google Docs document ID

        Returns:
            AccuracyTestResult with formatting preservation test results
        """
        test_id = f"formatting_preservation_{document_id}_{int(time.time())}"
        start_time = time.time()
        errors = []
        warnings = []
        metrics = {}

        try:
            # Convert document to Markdown
            conversion_result = self.converter.to_markdown(document_id)

            # Analyze formatting preservation
            formatting_metrics = self._analyze_formatting_preservation(
                conversion_result
            )

            # Calculate formatting preservation score
            formatting_score = self._calculate_formatting_preservation_score(
                formatting_metrics
            )

            metrics.update(formatting_metrics)
            metrics["formatting_score"] = formatting_score

            # Determine if test passed
            passed = formatting_score >= self.formatting_preservation_threshold

            if not passed:
                errors.append(
                    f"Formatting preservation score {formatting_score:.3f} below threshold {self.formatting_preservation_threshold}"
                )

        except Exception as e:
            logger.error(
                f"Formatting preservation test failed for document {document_id}: {e}"
            )
            errors.append(str(e))
            formatting_score = 0.0
            passed = False

        execution_time = time.time() - start_time

        result = AccuracyTestResult(
            test_id=test_id,
            document_id=document_id,
            test_type="formatting_preservation",
            passed=passed,
            accuracy_score=formatting_score,
            metrics=metrics,
            errors=errors,
            warnings=warnings,
            execution_time=execution_time,
            test_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        self.test_results.append(result)
        return result

    def run_comprehensive_test_suite(self, document_ids: List[str]) -> TestSuite:
        """Run comprehensive accuracy tests on multiple documents.

        Args:
            document_ids: List of Google Docs document IDs

        Returns:
            TestSuite with comprehensive test results
        """
        suite_start_time = time.time()
        all_tests = []

        for document_id in document_ids:
            # Run all test types for each document
            round_trip_test = self.test_round_trip_accuracy(document_id)
            content_test = self.test_content_preservation(document_id)
            formatting_test = self.test_formatting_preservation(document_id)

            all_tests.extend([round_trip_test, content_test, formatting_test])

        # Calculate overall metrics
        passed_tests = [test for test in all_tests if test.passed]
        pass_rate = len(passed_tests) / len(all_tests) if all_tests else 0.0

        overall_score = (
            sum(test.accuracy_score for test in all_tests) / len(all_tests)
            if all_tests
            else 0.0
        )

        execution_time = time.time() - suite_start_time

        return TestSuite(
            name="Comprehensive Accuracy Test Suite",
            description=f"Complete accuracy testing for {len(document_ids)} documents",
            tests=all_tests,
            overall_score=overall_score,
            pass_rate=pass_rate,
            execution_time=execution_time,
        )

    def _compare_conversions(
        self,
        original_conversion: ConversionResult,
        reconverted_conversion: ConversionResult,
        original_markdown: str,
        reconverted_markdown: str,
    ) -> Dict[str, Any]:
        """Compare original and reconverted conversions.

        Args:
            original_conversion: Original conversion result
            reconverted_conversion: Reconverted conversion result
            original_markdown: Original Markdown content
            reconverted_markdown: Reconverted Markdown content

        Returns:
            Dictionary with comparison metrics
        """
        metrics = {}

        # Text-based comparison
        original_lines = original_markdown.splitlines()
        reconverted_lines = reconverted_markdown.splitlines()

        # Calculate line-level accuracy
        import difflib

        matcher = difflib.SequenceMatcher(None, original_lines, reconverted_lines)
        line_similarity = matcher.ratio()

        # Calculate character-level accuracy
        char_matcher = difflib.SequenceMatcher(
            None, original_markdown, reconverted_markdown
        )
        char_similarity = char_matcher.ratio()

        # Calculate content hashes
        original_hash = hashlib.sha256(original_markdown.encode()).hexdigest()
        reconverted_hash = hashlib.sha256(reconverted_markdown.encode()).hexdigest()

        # Element-level comparison
        original_elements = len(original_conversion.elements)
        reconverted_elements = len(reconverted_conversion.elements)
        element_preservation = (
            1.0
            if original_elements == 0
            else min(reconverted_elements / original_elements, 1.0)
        )

        # Comment preservation
        original_comments = len(original_conversion.comments)
        reconverted_comments = len(reconverted_conversion.comments)
        comment_preservation = (
            1.0
            if original_comments == 0
            else min(reconverted_comments / original_comments, 1.0)
        )

        # Suggestion preservation
        original_suggestions = len(original_conversion.suggestions)
        reconverted_suggestions = len(reconverted_conversion.suggestions)
        suggestion_preservation = (
            1.0
            if original_suggestions == 0
            else min(reconverted_suggestions / original_suggestions, 1.0)
        )

        # Length comparison
        length_ratio = (
            len(reconverted_markdown) / len(original_markdown)
            if original_markdown
            else 1.0
        )

        metrics.update(
            {
                "line_similarity": line_similarity,
                "character_similarity": char_similarity,
                "content_hash_match": original_hash == reconverted_hash,
                "element_preservation": element_preservation,
                "comment_preservation": comment_preservation,
                "suggestion_preservation": suggestion_preservation,
                "length_ratio": length_ratio,
                "original_length": len(original_markdown),
                "reconverted_length": len(reconverted_markdown),
                "original_elements": original_elements,
                "reconverted_elements": reconverted_elements,
                "original_comments": original_comments,
                "reconverted_comments": reconverted_comments,
                "original_suggestions": original_suggestions,
                "reconverted_suggestions": reconverted_suggestions,
            }
        )

        return metrics

    def _calculate_overall_accuracy(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall accuracy score from metrics.

        Args:
            metrics: Dictionary of accuracy metrics

        Returns:
            Overall accuracy score (0.0 to 1.0)
        """
        # Weighted average of different accuracy measures
        weights = {
            "character_similarity": 0.4,
            "line_similarity": 0.3,
            "element_preservation": 0.15,
            "comment_preservation": 0.1,
            "suggestion_preservation": 0.05,
        }

        total_score = 0.0
        total_weight = 0.0

        for metric, weight in weights.items():
            if metric in metrics:
                total_score += metrics[metric] * weight
                total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def _analyze_content_preservation(
        self, conversion_result: ConversionResult
    ) -> Dict[str, Any]:
        """Analyze content preservation in conversion result.

        Args:
            conversion_result: ConversionResult to analyze

        Returns:
            Dictionary with content preservation metrics
        """
        metrics = {}

        # Text content analysis
        content = conversion_result.content

        # Count different content types
        lines = content.splitlines()
        headers = [line for line in lines if line.strip().startswith("#")]
        paragraphs = [
            line for line in lines if line.strip() and not line.strip().startswith("#")
        ]

        metrics.update(
            {
                "total_lines": len(lines),
                "header_count": len(headers),
                "paragraph_count": len(paragraphs),
                "total_characters": len(content),
                "total_words": len(content.split()),
                "conversion_accuracy": conversion_result.conversion_accuracy,
            }
        )

        # Element analysis
        element_types = {}
        for element in conversion_result.elements:
            element_type = element.element_type
            element_types[element_type] = element_types.get(element_type, 0) + 1

        metrics["element_types"] = element_types
        metrics["total_elements"] = len(conversion_result.elements)

        # Comment and suggestion analysis
        metrics["comments_extracted"] = len(conversion_result.comments)
        metrics["suggestions_extracted"] = len(conversion_result.suggestions)

        return metrics

    def _calculate_content_preservation_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate content preservation score.

        Args:
            metrics: Content preservation metrics

        Returns:
            Content preservation score (0.0 to 1.0)
        """
        # Base score from conversion accuracy
        base_score = metrics.get("conversion_accuracy", 0.0)

        # Bonus for preserved elements
        element_bonus = 0.0
        total_elements = metrics.get("total_elements", 0)
        if total_elements > 0:
            element_bonus = min(total_elements / 100, 0.1)  # Up to 10% bonus

        # Bonus for preserved comments and suggestions
        comment_bonus = min(
            metrics.get("comments_extracted", 0) / 10, 0.05
        )  # Up to 5% bonus
        suggestion_bonus = min(
            metrics.get("suggestions_extracted", 0) / 10, 0.05
        )  # Up to 5% bonus

        total_score = base_score + element_bonus + comment_bonus + suggestion_bonus

        return min(total_score, 1.0)

    def _analyze_formatting_preservation(
        self, conversion_result: ConversionResult
    ) -> Dict[str, Any]:
        """Analyze formatting preservation in conversion result.

        Args:
            conversion_result: ConversionResult to analyze

        Returns:
            Dictionary with formatting preservation metrics
        """
        metrics = {}

        # Count formatted elements
        formatted_elements = 0
        formatting_types = {}

        for element in conversion_result.elements:
            if element.formatting:
                formatted_elements += 1

                # Count different formatting types
                for format_type, format_value in element.formatting.items():
                    if format_value:  # Only count non-empty formatting
                        formatting_types[format_type] = (
                            formatting_types.get(format_type, 0) + 1
                        )

        metrics.update(
            {
                "formatted_elements": formatted_elements,
                "formatting_types": formatting_types,
                "total_formatting_applications": sum(formatting_types.values()),
                "formatting_diversity": len(formatting_types),
            }
        )

        # Analyze Markdown formatting preservation
        content = conversion_result.content

        # Count Markdown formatting elements
        bold_count = content.count("**")
        italic_count = content.count("*") - bold_count  # Subtract bold markers
        header_count = len(
            [line for line in content.splitlines() if line.strip().startswith("#")]
        )
        link_count = (
            content.count("[") if content.count("[") == content.count("]") else 0
        )

        metrics.update(
            {
                "markdown_bold": bold_count // 2,  # Pairs of **
                "markdown_italic": italic_count // 2,  # Pairs of *
                "markdown_headers": header_count,
                "markdown_links": link_count,
            }
        )

        return metrics

    def _calculate_formatting_preservation_score(
        self, metrics: Dict[str, Any]
    ) -> float:
        """Calculate formatting preservation score.

        Args:
            metrics: Formatting preservation metrics

        Returns:
            Formatting preservation score (0.0 to 1.0)
        """
        # Base score from formatting diversity
        formatting_diversity = metrics.get("formatting_diversity", 0)
        base_score = min(formatting_diversity / 10, 0.6)  # Up to 60% for diversity

        # Score for Markdown formatting preservation
        markdown_elements = (
            metrics.get("markdown_bold", 0)
            + metrics.get("markdown_italic", 0)
            + metrics.get("markdown_headers", 0)
            + metrics.get("markdown_links", 0)
        )

        markdown_score = min(markdown_elements / 20, 0.4)  # Up to 40% for Markdown

        total_score = base_score + markdown_score

        return min(total_score, 1.0)

    def generate_test_report(self, test_suite: TestSuite) -> str:
        """Generate a comprehensive test report.

        Args:
            test_suite: TestSuite to generate report for

        Returns:
            HTML report string
        """
        html_parts = []

        # Add CSS styles
        html_parts.append(
            """
        <style>
        .test-report {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .summary {
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
        }
        .metric {
            text-align: center;
            padding: 15px;
            background-color: #e9ecef;
            border-radius: 8px;
            min-width: 120px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }
        .metric-label {
            color: #6c757d;
            font-size: 14px;
        }
        .test-results {
            margin-top: 20px;
        }
        .test-item {
            background-color: #fff;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .test-passed {
            border-left: 4px solid #28a745;
        }
        .test-failed {
            border-left: 4px solid #dc3545;
        }
        .test-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .test-title {
            font-weight: bold;
            color: #495057;
        }
        .test-score {
            font-size: 18px;
            font-weight: bold;
        }
        .score-passed {
            color: #28a745;
        }
        .score-failed {
            color: #dc3545;
        }
        .test-details {
            font-size: 14px;
            color: #6c757d;
        }
        .error-list {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
        }
        .warning-list {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
        }
        </style>
        """
        )

        # Start report
        html_parts.append('<div class="test-report">')

        # Header
        html_parts.append(
            """
        <div class="header">
            <h1>Conversion Accuracy Test Report</h1>
            <h2>{test_suite.name}</h2>
            <p>{test_suite.description}</p>
        </div>
        """
        )

        # Summary metrics
        html_parts.append(
            """
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{test_suite.overall_score:.1%}</div>
                <div class="metric-label">Overall Score</div>
            </div>
            <div class="metric">
                <div class="metric-value">{test_suite.pass_rate:.1%}</div>
                <div class="metric-label">Pass Rate</div>
            </div>
            <div class="metric">
                <div class="metric-value">{len(test_suite.tests)}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric">
                <div class="metric-value">{test_suite.execution_time:.1f}s</div>
                <div class="metric-label">Execution Time</div>
            </div>
        </div>
        """
        )

        # Test results
        html_parts.append('<div class="test-results">')
        html_parts.append("<h3>Test Results</h3>")

        for test in test_suite.tests:
            test_class = "test-passed" if test.passed else "test-failed"
            score_class = "score-passed" if test.passed else "score-failed"

            html_parts.append(
                """
            <div class="test-item {test_class}">
                <div class="test-header">
                    <div class="test-title">{test.test_type.replace("_", " ").title()} - {test.document_id}</div>
                    <div class="test-score {score_class}">{test.accuracy_score:.1%}</div>
                </div>
                <div class="test-details">
                    Execution Time: {test.execution_time:.2f}s |
                    Test ID: {test.test_id} |
                    Timestamp: {test.test_timestamp}
                </div>
            """
            )

            # Add errors if any
            if test.errors:
                html_parts.append('<div class="error-list">')
                html_parts.append("<strong>Errors:</strong>")
                html_parts.append("<ul>")
                for error in test.errors:
                    html_parts.append(f"<li>{error}</li>")
                html_parts.append("</ul>")
                html_parts.append("</div>")

            # Add warnings if any
            if test.warnings:
                html_parts.append('<div class="warning-list">')
                html_parts.append("<strong>Warnings:</strong>")
                html_parts.append("<ul>")
                for warning in test.warnings:
                    html_parts.append(f"<li>{warning}</li>")
                html_parts.append("</ul>")
                html_parts.append("</div>")

            html_parts.append("</div>")

        html_parts.append("</div>")
        html_parts.append("</div>")

        return "".join(html_parts)

    def save_test_results(self, test_suite: TestSuite, output_path: Path):
        """Save test results to file.

        Args:
            test_suite: TestSuite to save
            output_path: Path to save results
        """
        # Save JSON results
        json_path = output_path / f"test_results_{int(time.time())}.json"
        with open(json_path, "w") as f:
            json.dump(test_suite.to_dict(), f, indent=2)

        # Save HTML report
        html_path = output_path / f"test_report_{int(time.time())}.html"
        html_report = self.generate_test_report(test_suite)
        with open(html_path, "w") as f:
            f.write(html_report)

        logger.info(f"Test results saved to {json_path}")
        logger.info(f"Test report saved to {html_path}")

    def get_test_history(
        self, document_id: Optional[str] = None
    ) -> List[AccuracyTestResult]:
        """Get test history with optional filtering.

        Args:
            document_id: Optional filter by document ID

        Returns:
            List of AccuracyTestResult objects
        """
        results = self.test_results

        if document_id:
            results = [r for r in results if r.document_id == document_id]

        return sorted(results, key=lambda r: r.test_timestamp, reverse=True)
