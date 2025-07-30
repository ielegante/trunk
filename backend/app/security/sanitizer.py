import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import bleach
import validators
from html_sanitizer import Sanitizer

logger = logging.getLogger(__name__)


class SanitizationLevel(Enum):
    """Levels of content sanitization"""

    STRICT = "strict"
    MODERATE = "moderate"
    PERMISSIVE = "permissive"
    CUSTOM = "custom"


class ContentType(Enum):
    """Types of content to sanitize"""

    HTML = "html"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    URL = "url"
    EMAIL = "email"
    FILENAME = "filename"
    CODE = "code"


@dataclass
class SanitizationResult:
    """Result of content sanitization"""

    sanitized_content: str
    original_content: str
    issues_found: List[str]
    changes_made: List[str]
    security_score: int  # 0-100, higher is safer
    is_safe: bool


class ContentSanitizer:
    """Comprehensive content sanitization for security"""

    def __init__(self):
        self.html_sanitizer = self._setup_html_sanitizer()
        self.markdown_patterns = self._setup_markdown_patterns()
        self.dangerous_patterns = self._setup_dangerous_patterns()

    def _setup_html_sanitizer(self) -> Sanitizer:
        """Set up HTML sanitizer with security-focused rules"""
        return Sanitizer(
            {
                "tags": {
                    "a",
                    "abbr",
                    "acronym",
                    "address",
                    "area",
                    "article",
                    "aside",
                    "b",
                    "bdi",
                    "bdo",
                    "big",
                    "blockquote",
                    "br",
                    "button",
                    "caption",
                    "center",
                    "cite",
                    "code",
                    "col",
                    "colgroup",
                    "dd",
                    "del",
                    "details",
                    "dfn",
                    "div",
                    "dl",
                    "dt",
                    "em",
                    "fieldset",
                    "figcaption",
                    "figure",
                    "footer",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "header",
                    "hgroup",
                    "hr",
                    "i",
                    "img",
                    "ins",
                    "kbd",
                    "label",
                    "legend",
                    "li",
                    "main",
                    "mark",
                    "nav",
                    "ol",
                    "p",
                    "pre",
                    "q",
                    "rp",
                    "rt",
                    "ruby",
                    "s",
                    "samp",
                    "section",
                    "small",
                    "span",
                    "strong",
                    "sub",
                    "summary",
                    "sup",
                    "table",
                    "tbody",
                    "td",
                    "tfoot",
                    "th",
                    "thead",
                    "time",
                    "tr",
                    "u",
                    "ul",
                    "var",
                    "wbr",
                },
                "attributes": {
                    "a": ["hre", "title"],
                    "abbr": ["title"],
                    "acronym": ["title"],
                    "img": ["src", "alt", "title", "width", "height"],
                    "blockquote": ["cite"],
                    "cite": ["title"],
                    "q": ["cite"],
                    "time": ["datetime"],
                },
                "empty": {"area", "br", "col", "hr", "img", "wbr"},
                "separate": {"a", "q", "blockquote"},
                "whitespace": {"normalize"},
                "add_nofollow": True,
                "autolink": False,
                "sanitize_hre": self._sanitize_href,
            }
        )

    def _setup_markdown_patterns(self) -> Dict[str, re.Pattern]:
        """Set up patterns for Markdown sanitization"""
        return {
            "script_tags": re.compile(
                r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL
            ),
            "javascript_links": re.compile(r"javascript:", re.IGNORECASE),
            "data_uris": re.compile(r"data:", re.IGNORECASE),
            "file_uris": re.compile(r"file:", re.IGNORECASE),
            "html_comments": re.compile(r"<!--.*?-->", re.DOTALL),
            "dangerous_protocols": re.compile(
                r"(javascript|data|file|vbscript):", re.IGNORECASE
            ),
            "html_entities": re.compile(r"&[a-zA-Z][a-zA-Z0-9]*;"),
            "suspicious_attributes": re.compile(r"(on\w+|style)\s*=", re.IGNORECASE),
        }

    def _setup_dangerous_patterns(self) -> Dict[str, re.Pattern]:
        """Set up patterns for detecting dangerous content"""
        return {
            "sql_injection": re.compile(
                r"(\bunion\b.*\bselect\b|\bselect\b.*\bfrom\b|\binsert\b.*\binto\b|\bupdate\b.*\bset\b|\bdelete\b.*\bfrom\b)",
                re.IGNORECASE,
            ),
            "xss_patterns": re.compile(
                r"(<script|javascript:|on\w+\s*=|<iframe|<object|<embed)", re.IGNORECASE
            ),
            "path_traversal": re.compile(r"\.\.[\\/]"),
            "command_injection": re.compile(
                r"(\||;|&|\$\(|\`|<|>|\{|\})", re.MULTILINE
            ),
            "suspicious_files": re.compile(
                r"\.(exe|bat|cmd|scr|pif|vbs|js|jar|com|dll|sys)$", re.IGNORECASE
            ),
        }

    def sanitize_content(
        self,
        content: str,
        content_type: ContentType,
        level: SanitizationLevel = SanitizationLevel.MODERATE,
        custom_rules: Optional[Dict] = None,
    ) -> SanitizationResult:
        """Sanitize content based on type and security level"""

        original_content = content
        issues_found = []
        changes_made = []

        # Detect dangerous patterns first
        dangerous_issues = self._detect_dangerous_patterns(content)
        issues_found.extend(dangerous_issues)

        # Apply type-specific sanitization
        if content_type == ContentType.HTML:
            sanitized = self._sanitize_html(content, level)
        elif content_type == ContentType.MARKDOWN:
            sanitized = self._sanitize_markdown(content, level)
        elif content_type == ContentType.PLAIN_TEXT:
            sanitized = self._sanitize_plain_text(content, level)
        elif content_type == ContentType.URL:
            sanitized = self._sanitize_url(content)
        elif content_type == ContentType.EMAIL:
            sanitized = self._sanitize_email(content)
        elif content_type == ContentType.FILENAME:
            sanitized = self._sanitize_filename(content)
        elif content_type == ContentType.CODE:
            sanitized = self._sanitize_code(content, level)
        else:
            sanitized = self._sanitize_plain_text(content, level)

        # Track changes
        if sanitized != original_content:
            changes_made.append(f"Content sanitized for {content_type.value}")

        # Calculate security score
        security_score = self._calculate_security_score(sanitized, issues_found)

        return SanitizationResult(
            sanitized_content=sanitized,
            original_content=original_content,
            issues_found=issues_found,
            changes_made=changes_made,
            security_score=security_score,
            is_safe=security_score >= 70 and len(dangerous_issues) == 0,
        )

    def _sanitize_html(self, content: str, level: SanitizationLevel) -> str:
        """Sanitize HTML content"""
        if level == SanitizationLevel.STRICT:
            # Strip all HTML tags
            return bleach.clean(content, tags=[], attributes={}, strip=True)
        elif level == SanitizationLevel.MODERATE:
            # Use secure HTML sanitizer
            return self.html_sanitizer.sanitize(content)
        else:  # PERMISSIVE
            # Use bleach with more permissive settings
            allowed_tags = bleach.ALLOWED_TAGS.union(
                {
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "div",
                    "span",
                    "img",
                    "table",
                    "tr",
                    "td",
                    "th",
                    "thead",
                    "tbody",
                    "pre",
                    "code",
                }
            )
            allowed_attributes = bleach.ALLOWED_ATTRIBUTES.copy()
            allowed_attributes.update(
                {
                    "img": ["src", "alt", "title", "width", "height"],
                    "*": ["class", "id"],
                }
            )
            return bleach.clean(
                content, tags=allowed_tags, attributes=allowed_attributes
            )

    def _sanitize_markdown(self, content: str, level: SanitizationLevel) -> str:
        """Sanitize Markdown content"""
        sanitized = content

        # Remove dangerous patterns
        for pattern_name, pattern in self.markdown_patterns.items():
            if pattern.search(sanitized):
                sanitized = pattern.sub("", sanitized)

        # Remove or escape HTML in markdown
        if level == SanitizationLevel.STRICT:
            sanitized = re.sub(r"<[^>]+>", "", sanitized)
        elif level == SanitizationLevel.MODERATE:
            # Escape HTML tags
            sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")

        # Sanitize links
        sanitized = self._sanitize_markdown_links(sanitized)

        return sanitized

    def _sanitize_plain_text(self, content: str, level: SanitizationLevel) -> str:
        """Sanitize plain text content"""
        sanitized = content

        # Remove control characters except newlines and tabs
        sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", sanitized)

        if level == SanitizationLevel.STRICT:
            # Remove all non-printable characters
            sanitized = re.sub(r"[^\x20-\x7E\n\r\t]", "", sanitized)

        return sanitized

    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL"""
        try:
            # Validate URL format
            if not validators.url(url):
                return ""

            parsed = urlparse(url)

            # Block dangerous protocols
            if parsed.scheme.lower() in ["javascript", "data", "file", "vbscript"]:
                return ""

            # Only allow http/https
            if parsed.scheme.lower() not in ["http", "https"]:
                return ""

            # Reconstruct URL with safe components
            safe_url = urlunparse(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    "",  # Remove fragment for security
                )
            )

            return safe_url

        except Exception:
            return ""

    def _sanitize_email(self, email: str) -> str:
        """Sanitize email address"""
        try:
            if validators.email(email):
                # Basic sanitization - lowercase and strip
                return email.lower().strip()
            return ""
        except Exception:
            return ""

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for security"""
        # Remove path traversal attempts
        sanitized = filename.replace("..", "").replace("/", "").replace("\\", "")

        # Remove dangerous characters
        sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', "", sanitized)

        # Limit length
        if len(sanitized) > 255:
            name, ext = (
                sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
            )
            sanitized = name[:250] + ("." + ext if ext else "")

        # Ensure it's not empty
        if not sanitized.strip():
            sanitized = "sanitized_file"

        return sanitized

    def _sanitize_code(self, content: str, level: SanitizationLevel) -> str:
        """Sanitize code content"""
        sanitized = content

        if level == SanitizationLevel.STRICT:
            # Remove potentially dangerous code patterns
            dangerous_keywords = [
                "eval",
                "exec",
                "import os",
                "import sys",
                "__import__",
                "subprocess",
                "system",
                "shell",
                "popen",
            ]

            for keyword in dangerous_keywords:
                sanitized = re.sub(
                    re.escape(keyword),
                    f'REMOVED_{keyword.replace(" ", "_")}',
                    sanitized,
                    flags=re.IGNORECASE,
                )

        return sanitized

    def _sanitize_markdown_links(self, content: str) -> str:
        """Sanitize links in Markdown content"""
        # Pattern to match markdown links [text](url)
        link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

        def replace_link(match):
            text = match.group(1)
            url = match.group(2)

            # Sanitize the URL
            safe_url = self._sanitize_url(url)
            if not safe_url:
                return text  # Return just the text if URL is unsafe

            return f"[{text}]({safe_url})"

        return link_pattern.sub(replace_link, content)

    def _sanitize_href(self, href: str) -> str:
        """Custom href sanitizer for HTML sanitizer"""
        return self._sanitize_url(href)

    def _detect_dangerous_patterns(self, content: str) -> List[str]:
        """Detect dangerous patterns in content"""
        issues = []

        for pattern_name, pattern in self.dangerous_patterns.items():
            if pattern.search(content):
                issues.append(f"Detected {pattern_name.replace('_', ' ')}")

        return issues

    def _calculate_security_score(self, content: str, issues: List[str]) -> int:
        """Calculate security score (0-100)"""
        base_score = 100

        # Deduct points for issues
        base_score -= len(issues) * 20

        # Deduct points for suspicious patterns
        if re.search(r"<script", content, re.IGNORECASE):
            base_score -= 30

        if re.search(r"javascript:", content, re.IGNORECASE):
            base_score -= 25

        if re.search(r"on\w+\s*=", content, re.IGNORECASE):
            base_score -= 20

        # Ensure score is within bounds
        return max(0, min(100, base_score))

    def validate_file_upload(
        self,
        filename: str,
        content: bytes,
        allowed_extensions: Optional[List[str]] = None,
        max_size: int = 10 * 1024 * 1024,  # 10MB default
    ) -> Dict[str, Any]:
        """Validate file upload for security"""
        validation_result = {
            "is_valid": True,
            "issues": [],
            "sanitized_filename": "",
            "file_info": {},
        }

        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        validation_result["sanitized_filename"] = safe_filename

        # Check file size
        if len(content) > max_size:
            validation_result["is_valid"] = False
            validation_result["issues"].append(
                f"File size ({len(content)} bytes) exceeds maximum ({max_size} bytes)"
            )

        # Check file extension
        if allowed_extensions:
            file_ext = (
                safe_filename.lower().split(".")[-1] if "." in safe_filename else ""
            )
            if file_ext not in [ext.lower().lstrip(".") for ext in allowed_extensions]:
                validation_result["is_valid"] = False
                validation_result["issues"].append(
                    f"File extension '.{file_ext}' not allowed"
                )

        # Check for dangerous file types
        dangerous_extensions = [
            "exe",
            "bat",
            "cmd",
            "scr",
            "pi",
            "vbs",
            "js",
            "jar",
            "com",
            "dll",
            "sys",
        ]
        file_ext = safe_filename.lower().split(".")[-1] if "." in safe_filename else ""
        if file_ext in dangerous_extensions:
            validation_result["is_valid"] = False
            validation_result["issues"].append(
                f"Dangerous file type detected: .{file_ext}"
            )

        # Basic content analysis
        try:
            # Check for executable signatures
            if content.startswith(b"MZ") or content.startswith(b"\x7fELF"):
                validation_result["is_valid"] = False
                validation_result["issues"].append("Executable file detected")

            # Check for script content in non-script files
            if file_ext not in ["js", "py", "sh", "bat"]:
                script_patterns = [b"<script", b"javascript:", b"<?php", b"#!/"]
                for pattern in script_patterns:
                    if pattern in content[:1024]:  # Check first 1KB
                        validation_result["issues"].append(
                            "Script content detected in non-script file"
                        )
                        break

        except Exception as e:
            validation_result["issues"].append(f"Content analysis failed: {str(e)}")

        validation_result["file_info"] = {
            "original_filename": filename,
            "sanitized_filename": safe_filename,
            "size": len(content),
            "extension": file_ext,
        }

        return validation_result

    def sanitize_batch_content(
        self,
        content_items: List[Dict[str, Any]],
        global_level: SanitizationLevel = SanitizationLevel.MODERATE,
    ) -> List[SanitizationResult]:
        """Sanitize multiple content items in batch"""
        results = []

        for item in content_items:
            content = item.get("content", "")
            content_type = ContentType(item.get("type", "plain_text"))
            level = SanitizationLevel(item.get("level", global_level.value))

            try:
                result = self.sanitize_content(content, content_type, level)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to sanitize content item: {str(e)}")
                results.append(
                    SanitizationResult(
                        sanitized_content="",
                        original_content=content,
                        issues_found=[f"Sanitization error: {str(e)}"],
                        changes_made=[],
                        security_score=0,
                        is_safe=False,
                    )
                )

        return results
