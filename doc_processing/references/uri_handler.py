"""URI handling and resolution for document references."""

import re
from pathlib import Path
from typing import Any, Dict, Optional


class URIHandler:
    """Handles URI resolution and validation for document references."""

    def __init__(self, repository_path: Path):
        """Initialize URI handler for a repository.

        Args:
            repository_path: Path to the document repository
        """
        self.repository_path = repository_path
        self.uri_schemes = {
            "trunk": self._resolve_trunk_uri,
            "file": self._resolve_file_uri,
            "http": self._resolve_http_uri,
            "https": self._resolve_https_uri,
        }

    def resolve_uri(self, uri: str) -> Optional[Dict[str, Any]]:
        """Resolve a URI to its target resource.

        Args:
            uri: URI string to resolve

        Returns:
            Dictionary with resolution information or None if invalid
        """
        scheme = self._extract_scheme(uri)
        if scheme not in self.uri_schemes:
            return None

        return self.uri_schemes[scheme](uri)

    def _extract_scheme(self, uri: str) -> Optional[str]:
        """Extract the scheme from a URI.

        Args:
            uri: URI string

        Returns:
            Scheme name or None if no valid scheme found
        """
        match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):\/\/", uri)
        if match:
            return match.group(1).lower()

        # Handle relative paths as file URIs
        if not uri.startswith("/") and "://" not in uri:
            return "file"

        return None

    def _resolve_trunk_uri(self, uri: str) -> Dict[str, Any]:
        """Resolve trunk:// URIs for internal document references.

        Args:
            uri: Trunk URI to resolve

        Returns:
            Resolution information
        """
        # Extract path from trunk://path/to/document
        path_part = uri.replace("trunk://", "")
        full_path = self.repository_path / path_part

        return {
            "type": "trunk_document",
            "path": str(full_path),
            "exists": full_path.exists(),
            "relative_path": path_part,
        }

    def _resolve_file_uri(self, uri: str) -> Dict[str, Any]:
        """Resolve file:// URIs and relative file paths.

        Args:
            uri: File URI to resolve

        Returns:
            Resolution information
        """
        if uri.startswith("file://"):
            file_path = Path(uri.replace("file://", ""))
        else:
            # Relative path
            file_path = self.repository_path / uri

        resolved_path = file_path.resolve()
        is_relative = str(file_path) != str(resolved_path)

        return {
            "type": "file",
            "path": str(resolved_path),
            "exists": file_path.exists(),
            "is_relative": is_relative,
        }

    def _resolve_http_uri(self, uri: str) -> Dict[str, Any]:
        """Resolve HTTP URIs.

        Args:
            uri: HTTP URI to resolve

        Returns:
            Resolution information
        """
        return {
            "type": "http",
            "url": uri,
            "accessible": False,  # TODO: Implement HTTP accessibility check
        }

    def _resolve_https_uri(self, uri: str) -> Dict[str, Any]:
        """Resolve HTTPS URIs.

        Args:
            uri: HTTPS URI to resolve

        Returns:
            Resolution information
        """
        return {
            "type": "https",
            "url": uri,
            "accessible": False,  # TODO: Implement HTTPS accessibility check
        }

    def create_trunk_uri(self, document_path: str) -> str:
        """Create a trunk:// URI for a document path.

        Args:
            document_path: Path to the document relative to repository

        Returns:
            Trunk URI string
        """
        # Normalize path separators
        normalized_path = document_path.replace("\\", "/")
        if normalized_path.startswith("/"):
            normalized_path = normalized_path[1:]

        return f"trunk://{normalized_path}"
