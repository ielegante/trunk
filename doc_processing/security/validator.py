"""Security validators for input validation and sanitization."""

import hashlib
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class InputValidator:
    """Validates and sanitizes user inputs for security."""

    # Safe file extensions for document processing
    ALLOWED_EXTENSIONS = {
        ".pd",
        ".doc",
        ".docx",
        ".txt",
        ".md",
        ".gdoc",
        ".odt",
        ".rt",
        ".tex",
        ".html",
        ".xml",
    }

    # Maximum file sizes (in bytes)
    MAX_FILE_SIZES = {
        ".pd": 100 * 1024 * 1024,  # 100MB
        ".doc": 50 * 1024 * 1024,  # 50MB
        ".docx": 50 * 1024 * 1024,  # 50MB
        "default": 25 * 1024 * 1024,  # 25MB
    }

    # Dangerous patterns in filenames
    DANGEROUS_PATTERNS = [
        r"\.\./",  # Path traversal
        r"\.\.\\",  # Windows path traversal
        r"^/",  # Absolute paths
        r"^[A-Za-z]:",  # Windows absolute paths
        r"\x00",  # Null bytes
        r'[<>:"|?*]',  # Invalid Windows characters
        r"[\x00-\x1f]",  # Control characters
    ]

    # Suspicious content patterns
    SUSPICIOUS_CONTENT = [
        r"<script[^>]*>.*?</script>",  # Scripts
        r"javascript:",  # JavaScript URLs
        r"vbscript:",  # VBScript URLs
        r"file:///",  # File URLs
        r"data:.*base64",  # Data URLs
    ]

    @classmethod
    def validate_filename(cls, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate filename for security issues.

        Args:
            filename: Filename to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not filename:
            return False, "Filename cannot be empty"

        # Check length
        if len(filename) > 255:
            return False, "Filename too long (max 255 characters)"

        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, filename):
                logger.warning(f"Dangerous pattern detected in filename: {filename}")
                return False, "Invalid filename: contains dangerous pattern"

        # Check extension
        ext = Path(filename).suffix.lower()
        if ext and ext not in cls.ALLOWED_EXTENSIONS:
            return False, f"File type not allowed: {ext}"

        # Sanitize filename
        safe_filename = cls.sanitize_filename(filename)
        if safe_filename != filename:
            logger.info(f"Filename sanitized: {filename} -> {safe_filename}")

        return True, None

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename by removing dangerous characters.

        Args:
            filename: Filename to sanitize

        Returns:
            Sanitized filename
        """
        # Remove path components
        filename = os.path.basename(filename)

        # Replace dangerous characters
        filename = re.sub(r'[<>:"|?*\x00-\x1f]', "_", filename)

        # Remove multiple dots (except for extension)
        parts = filename.split(".")
        if len(parts) > 2:
            name = "_".join(parts[:-1])
            ext = parts[-1]
            filename = f"{name}.{ext}"

        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            max_name_length = 255 - len(ext)
            filename = name[:max_name_length] + ext

        return filename

    @classmethod
    def validate_file_size(
        cls, file_size: int, file_extension: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate file size against limits.

        Args:
            file_size: Size in bytes
            file_extension: File extension

        Returns:
            Tuple of (is_valid, error_message)
        """
        max_size = cls.MAX_FILE_SIZES.get(
            file_extension.lower(), cls.MAX_FILE_SIZES["default"]
        )

        if file_size > max_size:
            size_mb = file_size / (1024 * 1024)
            max_mb = max_size / (1024 * 1024)
            return False, f"File too large: {size_mb:.1f}MB (max {max_mb:.1f}MB)"

        if file_size == 0:
            return False, "File is empty"

        return True, None

    @classmethod
    def validate_file_content(
        cls, content: bytes, mime_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate file content for security issues.

        Args:
            content: File content
            mime_type: MIME type if known

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for null bytes
        if b"\x00" in content:
            return False, "File contains null bytes"

        # Convert to string for pattern matching
        try:
            text_content = content.decode("utf-8", errors="ignore")
        except Exception:
            # Binary content, skip text validation
            return True, None

        # Check for suspicious patterns
        for pattern in cls.SUSPICIOUS_CONTENT:
            if re.search(pattern, text_content, re.IGNORECASE):
                logger.warning("Suspicious content pattern detected")
                return False, "File contains potentially malicious content"

        return True, None

    @classmethod
    def validate_path(
        cls, path: Union[str, Path], base_path: Optional[Path] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate file path for security issues.

        Args:
            path: Path to validate
            base_path: Base path to restrict access to

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            path = Path(path).resolve()

            # Check if path exists
            if not path.exists():
                return False, "Path does not exist"

            # Check base path restriction
            if base_path:
                base_path = Path(base_path).resolve()
                try:
                    path.relative_to(base_path)
                except ValueError:
                    return False, "Path is outside allowed directory"

            # Check if it's a symlink
            if path.is_symlink():
                link_target = path.readlink()
                if base_path:
                    try:
                        link_target.relative_to(base_path)
                    except ValueError:
                        return False, "Symlink points outside allowed directory"

            return True, None

        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False, f"Invalid path: {str(e)}"


class SecurityValidator:
    """Advanced security validation for document processing."""

    # Known malicious file signatures (magic bytes)
    MALICIOUS_SIGNATURES = {
        b"MZ": "Executable file",  # Windows EXE
        b"\x7fELF": "ELF executable",  # Linux executable
        b"#!/": "Shell script",
        b"<script": "Script file",
    }

    # Allowed MIME types
    ALLOWED_MIME_TYPES = {
        "application/pd",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "text/html",
        "text/xml",
        "application/vnd.google-apps.document",
    }

    @classmethod
    def check_file_signature(cls, content: bytes) -> Tuple[bool, Optional[str]]:
        """Check file signature for malicious content.

        Args:
            content: File content

        Returns:
            Tuple of (is_safe, detected_type)
        """
        if len(content) < 4:
            return True, None

        # Check against known malicious signatures
        for signature, file_type in cls.MALICIOUS_SIGNATURES.items():
            if content.startswith(signature):
                logger.warning(f"Malicious file signature detected: {file_type}")
                return False, file_type

        return True, None

    @classmethod
    def validate_mime_type(
        cls, file_path: str, content: Optional[bytes] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate MIME type of file.

        Args:
            file_path: Path to file
            content: File content for magic byte checking

        Returns:
            Tuple of (is_valid, detected_mime_type)
        """
        # Guess MIME type from filename
        mime_type, _ = mimetypes.guess_type(file_path)

        if mime_type and mime_type not in cls.ALLOWED_MIME_TYPES:
            return False, mime_type

        # Additional validation with python-magic if available
        try:
            import magic

            if content:
                detected_type = magic.from_buffer(content, mime=True)
                if detected_type not in cls.ALLOWED_MIME_TYPES:
                    return False, detected_type
        except ImportError:
            pass  # python-magic not available

        return True, mime_type

    @classmethod
    def check_archive_bombs(
        cls, file_size: int, uncompressed_size: int, ratio_threshold: float = 100.0
    ) -> Tuple[bool, Optional[str]]:
        """Check for potential archive/compression bombs.

        Args:
            file_size: Compressed file size
            uncompressed_size: Uncompressed size
            ratio_threshold: Maximum compression ratio allowed

        Returns:
            Tuple of (is_safe, warning_message)
        """
        if uncompressed_size == 0:
            return True, None

        ratio = uncompressed_size / file_size

        if ratio > ratio_threshold:
            return False, f"Suspicious compression ratio: {ratio:.1f}:1"

        # Check absolute size
        if uncompressed_size > 1024 * 1024 * 1024:  # 1GB
            return (
                False,
                f"Uncompressed size too large: {uncompressed_size / (1024*1024):.1f}MB",
            )

        return True, None

    @classmethod
    def validate_metadata(cls, metadata: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Validate and sanitize document metadata.

        Args:
            metadata: Document metadata

        Returns:
            Tuple of (is_valid, sanitized_metadata)
        """
        sanitized = {}

        # Whitelist of allowed metadata fields
        allowed_fields = {
            "title",
            "author",
            "created_date",
            "modified_date",
            "page_count",
            "word_count",
            "language",
            "subject",
            "keywords",
            "category",
            "comments",
        }

        for key, value in metadata.items():
            if key not in allowed_fields:
                logger.warning(f"Dropping unallowed metadata field: {key}")
                continue

            # Sanitize string values
            if isinstance(value, str):
                # Remove control characters
                value = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", value)

                # Limit length
                if len(value) > 1000:
                    value = value[:1000]

            # Validate lists
            elif isinstance(value, list):
                value = [
                    str(item)[:100] for item in value[:10]
                ]  # Limit items and length

            sanitized[key] = value

        return True, sanitized

    @classmethod
    def generate_file_hash(cls, content: bytes, algorithm: str = "sha256") -> str:
        """Generate secure hash of file content.

        Args:
            content: File content
            algorithm: Hash algorithm to use

        Returns:
            Hex digest of hash
        """
        hash_func = hashlib.new(algorithm)
        hash_func.update(content)
        return hash_func.hexdigest()

    @classmethod
    def validate_api_input(
        cls, data: Dict[str, Any], schema: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate API input against schema.

        Args:
            data: Input data
            schema: Validation schema

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Simple schema validation (in production, use jsonschema)
        for field, rules in schema.items():
            if rules.get("required", False) and field not in data:
                return False, f"Missing required field: {field}"

            if field in data:
                value = data[field]

                # Type validation
                expected_type = rules.get("type")
                if expected_type and not isinstance(value, expected_type):
                    return (
                        False,
                        f"Invalid type for {field}: expected {expected_type.__name__}",
                    )

                # Length validation for strings
                if isinstance(value, str):
                    max_length = rules.get("max_length")
                    if max_length and len(value) > max_length:
                        return False, f"{field} too long: max {max_length} characters"

                    # Pattern validation
                    pattern = rules.get("pattern")
                    if pattern and not re.match(pattern, value):
                        return False, f"{field} does not match required pattern"

                # Range validation for numbers
                if isinstance(value, (int, float)):
                    min_val = rules.get("min")
                    max_val = rules.get("max")
                    if min_val is not None and value < min_val:
                        return False, f"{field} below minimum value: {min_val}"
                    if max_val is not None and value > max_val:
                        return False, f"{field} above maximum value: {max_val}"

        return True, None
