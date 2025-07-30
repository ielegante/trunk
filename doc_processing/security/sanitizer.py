"""Document and path sanitization for security."""

import html
import logging
import os
import re
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PathSanitizer:
    """Sanitizes file paths for secure file operations."""

    @staticmethod
    def sanitize_path(path: str, base_dir: Optional[str] = None) -> str:
        """Sanitize a file path to prevent directory traversal.

        Args:
            path: Path to sanitize
            base_dir: Base directory to resolve relative paths

        Returns:
            Sanitized path string
        """
        # Convert to Path object for proper handling
        path_obj = Path(path)

        # Get individual parts and filter out dangerous components
        safe_parts = []
        for part in path_obj.parts:
            # Skip empty, current directory, or parent directory references
            if part in ("", ".", ".."):
                continue

            # Remove null bytes and control characters
            part = part.replace("\x00", "")
            part = re.sub(r"[\x01-\x1f\x7f]", "", part)

            # Skip if still empty after cleaning
            if part:
                safe_parts.append(part)

        # Reconstruct path
        if safe_parts:
            safe_path = Path(*safe_parts)
        else:
            safe_path = Path(".")

        # If base directory provided, ensure path is within it
        if base_dir:
            base_path = Path(base_dir).resolve()
            try:
                # Resolve the safe path relative to base
                full_path = (base_path / safe_path).resolve()

                # Ensure it's within base directory
                full_path.relative_to(base_path)

                return str(full_path)
            except ValueError:
                # Path would escape base directory
                logger.warning(f"Path traversal attempt blocked: {path}")
                return str(base_path)

        return str(safe_path)

    @staticmethod
    def is_safe_path(path: str, base_dir: str) -> bool:
        """Check if a path is safe (within base directory).

        Args:
            path: Path to check
            base_dir: Base directory

        Returns:
            True if path is safe
        """
        try:
            base_path = Path(base_dir).resolve()
            check_path = Path(path).resolve()

            # Check if path is within base directory
            check_path.relative_to(base_path)

            # Check for symlinks that might escape
            if check_path.is_symlink():
                link_target = check_path.readlink()
                link_target.relative_to(base_path)

            return True
        except (ValueError, OSError):
            return False

    @staticmethod
    def create_safe_filename(filename: str, max_length: int = 255) -> str:
        """Create a safe filename from user input.

        Args:
            filename: Original filename
            max_length: Maximum filename length

        Returns:
            Safe filename
        """
        # Get base name without path
        filename = os.path.basename(filename)

        # Normalize unicode
        filename = unicodedata.normalize("NFKD", filename)

        # Keep only safe characters
        # Allow alphanumeric, spaces, hyphens, underscores, and dots
        filename = re.sub(r"[^a-zA-Z0-9\s\-_.]", "", filename)

        # Replace multiple spaces with single space
        filename = re.sub(r"\s+", " ", filename)

        # Remove leading/trailing spaces and dots
        filename = filename.strip(" .")

        # Ensure filename is not empty
        if not filename:
            filename = "unnamed_file"

        # Split name and extension
        parts = filename.rsplit(".", 1)
        if len(parts) == 2:
            name, ext = parts
            # Ensure extension is safe
            ext = re.sub(r"[^a-zA-Z0-9]", "", ext)[:10]  # Limit extension length
        else:
            name = parts[0]
            ext = ""

        # Truncate name if needed
        if ext:
            max_name_length = max_length - len(ext) - 1
            name = name[:max_name_length]
            filename = f"{name}.{ext}"
        else:
            filename = name[:max_length]

        return filename


class DocumentSanitizer:
    """Sanitizes document content for security."""

    # Patterns that might indicate malicious content
    MALICIOUS_PATTERNS = {
        "script_tags": re.compile(
            r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL
        ),
        "event_handlers": re.compile(r"\bon\w+\s*=", re.IGNORECASE),
        "javascript_urls": re.compile(r"javascript:", re.IGNORECASE),
        "data_urls": re.compile(r'data:[^,]+,[^"\'>\s]+', re.IGNORECASE),
        "object_tags": re.compile(
            r"<object[^>]*>.*?</object>", re.IGNORECASE | re.DOTALL
        ),
        "embed_tags": re.compile(r"<embed[^>]*>", re.IGNORECASE),
        "iframe_tags": re.compile(
            r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL
        ),
        "form_tags": re.compile(r"<form[^>]*>.*?</form>", re.IGNORECASE | re.DOTALL),
        "meta_refresh": re.compile(
            r"<meta[^>]*http-equiv[^>]*refresh[^>]*>", re.IGNORECASE
        ),
    }

    # Safe HTML tags for document content
    SAFE_TAGS = {
        "p",
        "div",
        "span",
        "br",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
        "blockquote",
        "pre",
        "code",
        "a",
        "img",
    }

    # Safe HTML attributes
    SAFE_ATTRIBUTES = {
        "class",
        "id",
        "style",
        "hre",
        "src",
        "alt",
        "title",
        "width",
        "height",
        "colspan",
        "rowspan",
    }

    @classmethod
    def sanitize_html(
        cls, html_content: str, allow_styles: bool = False, allow_links: bool = True
    ) -> str:
        """Sanitize HTML content by removing dangerous elements.

        Args:
            html_content: HTML content to sanitize
            allow_styles: Whether to allow style attributes
            allow_links: Whether to allow links

        Returns:
            Sanitized HTML content
        """
        if not html_content:
            return ""

        # Remove dangerous patterns
        for pattern_name, pattern in cls.MALICIOUS_PATTERNS.items():
            html_content = pattern.sub("", html_content)

        # Additional link sanitization
        if not allow_links:
            html_content = re.sub(
                r"<a[^>]*>.*?</a>", "", html_content, flags=re.IGNORECASE | re.DOTALL
            )

        # Remove style attributes if not allowed
        if not allow_styles:
            html_content = re.sub(
                r'\sstyle\s*=\s*["\'][^"\']*["\']',
                "",
                html_content,
                flags=re.IGNORECASE,
            )

        # Escape remaining content
        # Note: In production, use a proper HTML sanitization library like bleach
        return html_content

    @classmethod
    def sanitize_text(cls, text: str, remove_urls: bool = False) -> str:
        """Sanitize plain text content.

        Args:
            text: Text to sanitize
            remove_urls: Whether to remove URLs

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Remove null bytes and control characters
        text = text.replace("\x00", "")
        text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Normalize whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)

        # Remove URLs if requested
        if remove_urls:
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            text = re.sub(url_pattern, "[URL_REMOVED]", text)

        # Remove potential script injections in text
        text = re.sub(
            r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
        )

        return text.strip()

    @classmethod
    def sanitize_markdown(cls, markdown: str) -> str:
        """Sanitize Markdown content.

        Args:
            markdown: Markdown content to sanitize

        Returns:
            Sanitized markdown
        """
        if not markdown:
            return ""

        # Remove HTML tags from markdown
        markdown = re.sub(r"<[^>]+>", "", markdown)

        # Sanitize links - remove javascript: and data: URLs
        markdown = re.sub(
            r"\[([^\]]+)\]\(javascript:[^)]*\)",
            r"[\1](#)",
            markdown,
            flags=re.IGNORECASE,
        )
        markdown = re.sub(
            r"\[([^\]]+)\]\(data:[^)]*\)", r"[\1](#)", markdown, flags=re.IGNORECASE
        )

        # Remove potential XSS in code blocks
        markdown = re.sub(
            r"```.*?<script.*?```",
            "```[SCRIPT_REMOVED]```",
            markdown,
            flags=re.IGNORECASE | re.DOTALL,
        )

        return markdown

    @classmethod
    def escape_special_chars(cls, text: str, escape_quotes: bool = True) -> str:
        """Escape special characters for safe output.

        Args:
            text: Text to escape
            escape_quotes: Whether to escape quotes

        Returns:
            Escaped text
        """
        # HTML escape
        text = html.escape(text, quote=escape_quotes)

        # Additional escaping for common injection points
        text = text.replace("`", "\\`")  # Backticks
        text = text.replace("$", "\\$")  # Dollar signs (command substitution)

        return text

    @classmethod
    def remove_metadata(cls, content: str, content_type: str = "text") -> str:
        """Remove potentially sensitive metadata from content.

        Args:
            content: Content to clean
            content_type: Type of content ('text', 'html', 'markdown')

        Returns:
            Content with metadata removed
        """
        # Patterns for common metadata
        metadata_patterns = [
            # Author information
            re.compile(r"(?:Author|Created by|Written by):\s*[^\n]+", re.IGNORECASE),
            # Timestamps
            re.compile(
                r"(?:Created|Modified|Updated):\s*\d{4}-\d{2}-\d{2}[^\n]*",
                re.IGNORECASE,
            ),
            # File paths
            re.compile(r"[A-Z]:\\[^\n]+", re.IGNORECASE),  # Windows paths
            re.compile(r"/(?:home|usr|Users)/[^\s]+"),  # Unix paths
            # Email addresses
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            # IP addresses
            re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            # Phone numbers (US format)
            re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        ]

        for pattern in metadata_patterns:
            content = pattern.sub("[REDACTED]", content)

        return content

    @classmethod
    def validate_encoding(cls, content: bytes) -> Tuple[bool, Optional[str]]:
        """Validate content encoding and detect issues.

        Args:
            content: Content bytes to validate

        Returns:
            Tuple of (is_valid, detected_encoding)
        """
        # Common encodings to try
        encodings = ["utf-8", "latin-1", "cp1252", "utf-16"]

        for encoding in encodings:
            try:
                decoded = content.decode(encoding)

                # Check for suspicious Unicode characters
                suspicious_chars = [
                    "\u202e",  # Right-to-left override
                    "\ufef",  # Zero-width no-break space
                    "\u200b",  # Zero-width space
                    "\u2060",  # Word joiner
                ]

                for char in suspicious_chars:
                    if char in decoded:
                        logger.warning(
                            f"Suspicious Unicode character detected: U+{ord(char):04X}"
                        )

                return True, encoding

            except UnicodeDecodeError:
                continue

        return False, None

    @classmethod
    def clean_for_storage(
        cls, data: Dict[str, Any], sensitive_fields: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """Clean data dictionary for safe storage.

        Args:
            data: Data to clean
            sensitive_fields: Fields to redact

        Returns:
            Cleaned data dictionary
        """
        if sensitive_fields is None:
            sensitive_fields = {
                "password",
                "token",
                "secret",
                "key",
                "ssn",
                "credit_card",
            }

        cleaned = {}

        for key, value in data.items():
            # Redact sensitive fields
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                cleaned[key] = "[REDACTED]"
            elif isinstance(value, str):
                # Clean string values
                cleaned[key] = cls.sanitize_text(value)
            elif isinstance(value, dict):
                # Recursive cleaning
                cleaned[key] = cls.clean_for_storage(value, sensitive_fields)
            elif isinstance(value, list):
                # Clean list items
                cleaned[key] = [
                    (
                        cls.clean_for_storage(item, sensitive_fields)
                        if isinstance(item, dict)
                        else (
                            cls.sanitize_text(str(item))
                            if isinstance(item, str)
                            else item
                        )
                    )
                    for item in value
                ]
            else:
                cleaned[key] = value

        return cleaned
