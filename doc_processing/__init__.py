"""
Document Processing Module for Trunk Legal Git

This module provides document conversion, template management, and cross-document
reference systems for legal document management.
"""

__version__ = "0.1.0"
__author__ = "Trunk Development Team"

# Lazy imports to avoid dependency issues during testing
__all__ = [
    "GoogleDocsConverter",
    "WordConverter",
    "CrossDocumentReferenceManager",
    "TemplateManager",
    "GoogleDriveClient",
    "PermissionMapper",
    "GitPermissionManager",
    "PermissionSyncManager",
    "BetaTestingFramework",
    "FeedbackCollector",
    "TestCoordinator",
    "TestingAnalytics",
]
