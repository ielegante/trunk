"""Template management system for legal document templates."""

import hashlib
import json
import logging
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TemplateMetadata:
    """Metadata for a document template."""

    template_id: str
    name: str
    description: str
    category: str  # e.g., "contracts", "agreements", "forms"
    version: str
    created_by: str
    created_at: datetime
    modified_by: str
    modified_at: datetime
    tags: List[str] = field(default_factory=list)
    fields: List[Dict[str, Any]] = field(
        default_factory=list
    )  # Template fields/variables
    dependencies: List[str] = field(default_factory=list)  # Other template IDs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["modified_at"] = self.modified_at.isoformat()
        return data


@dataclass
class TemplateField:
    """Represents a field/variable in a template."""

    field_id: str
    name: str
    field_type: str  # text, date, number, choice, etc.
    description: str
    required: bool = True
    default_value: Optional[Any] = None
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    placeholder: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class TemplateVersion:
    """Represents a version of a template."""

    version_id: str
    version_number: str
    commit_hash: str
    author: str
    timestamp: datetime
    message: str
    changes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class TemplateRelationship:
    """Tracks relationships between templates and documents."""

    parent_template_id: str
    child_document_id: str
    relationship_type: str  # "forked", "derived", "referenced"
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class TemplateManager:
    """Manages document templates with version control."""

    def __init__(self, templates_dir: Union[str, Path], git_backend=None):
        """Initialize template manager.

        Args:
            templates_dir: Directory for storing templates
            git_backend: Optional git backend for version control
        """
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.git_backend = git_backend

        # Create subdirectories
        self.metadata_dir = self.templates_dir / ".metadata"
        self.metadata_dir.mkdir(exist_ok=True)

        self.relationships_file = self.metadata_dir / "relationships.json"
        self.index_file = self.metadata_dir / "templates_index.json"

        # Load existing data
        self._load_index()
        self._load_relationships()

    def create_template(
        self,
        name: str,
        content: str,
        category: str,
        description: str,
        author: str,
        tags: Optional[List[str]] = None,
        fields: Optional[List[TemplateField]] = None,
    ) -> TemplateMetadata:
        """Create a new template.

        Args:
            name: Template name
            content: Template content
            category: Template category
            description: Template description
            author: Author name
            tags: Optional tags
            fields: Optional template fields

        Returns:
            TemplateMetadata for the created template
        """
        # Generate template ID
        template_id = self._generate_template_id(name, category)

        # Check if template already exists
        if template_id in self.templates_index:
            raise ValueError(
                f"Template '{name}' already exists in category '{category}'"
            )

        # Create template directory
        template_dir = self._get_template_dir(template_id)
        template_dir.mkdir(parents=True, exist_ok=True)

        # Save template content
        template_file = template_dir / "template.md"
        with open(template_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Create metadata
        metadata = TemplateMetadata(
            template_id=template_id,
            name=name,
            description=description,
            category=category,
            version="1.0.0",
            created_by=author,
            created_at=datetime.now(),
            modified_by=author,
            modified_at=datetime.now(),
            tags=tags or [],
            fields=[f.to_dict() for f in (fields or [])],
        )

        # Save metadata
        self._save_template_metadata(template_id, metadata)

        # Update index
        self.templates_index[template_id] = metadata
        self._save_index()

        # Git commit if available
        if self.git_backend:
            self._git_commit_template(template_id, f"Create template: {name}")

        logger.info(f"Created template: {name} (ID: {template_id})")
        return metadata

    def fork_template(
        self,
        template_id: str,
        document_name: str,
        document_path: Path,
        author: str,
        modifications: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, TemplateRelationship]:
        """Fork a template to create a new document.

        Args:
            template_id: ID of template to fork
            document_name: Name for the new document
            document_path: Path where document should be created
            author: Author creating the fork
            modifications: Optional field values to apply

        Returns:
            Tuple of (document_id, relationship)
        """
        # Verify template exists
        if template_id not in self.templates_index:
            raise ValueError(f"Template not found: {template_id}")

        # Load template
        template_content = self._load_template_content(template_id)
        metadata = self.templates_index[template_id]

        # Apply modifications if provided
        if modifications:
            template_content = self._apply_template_modifications(
                template_content, metadata.fields, modifications
            )

        # Generate document ID
        document_id = f"doc_{hashlib.sha256(f'{document_name}_{datetime.now().isoformat()}'.encode()).hexdigest()[:12]}"

        # Create document
        document_path = Path(document_path)
        document_path.parent.mkdir(parents=True, exist_ok=True)

        with open(document_path, "w", encoding="utf-8") as f:
            f.write(template_content)

        # Create relationship
        relationship = TemplateRelationship(
            parent_template_id=template_id,
            child_document_id=document_id,
            relationship_type="forked",
            created_at=datetime.now(),
            metadata={
                "document_name": document_name,
                "document_path": str(document_path),
                "author": author,
                "modifications": modifications or {},
            },
        )

        # Save relationship
        self.relationships.append(relationship)
        self._save_relationships()

        logger.info(f"Forked template {template_id} to create document {document_id}")
        return document_id, relationship

    def update_template(
        self,
        template_id: str,
        content: str,
        author: str,
        message: str,
        version_increment: str = "minor",  # major, minor, patch
    ) -> TemplateVersion:
        """Update an existing template.

        Args:
            template_id: Template ID to update
            content: New template content
            author: Author making the update
            message: Commit message
            version_increment: How to increment version

        Returns:
            TemplateVersion for the update
        """
        # Verify template exists
        if template_id not in self.templates_index:
            raise ValueError(f"Template not found: {template_id}")

        metadata = self.templates_index[template_id]

        # Increment version
        new_version = self._increment_version(metadata.version, version_increment)

        # Save new content
        template_dir = self._get_template_dir(template_id)
        template_file = template_dir / "template.md"

        # Backup old version
        backup_file = template_dir / f"template_v{metadata.version}.md"
        shutil.copy2(template_file, backup_file)

        # Write new content
        with open(template_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Update metadata
        metadata.version = new_version
        metadata.modified_by = author
        metadata.modified_at = datetime.now()

        # Create version record
        version = TemplateVersion(
            version_id=f"{template_id}_v{new_version}",
            version_number=new_version,
            commit_hash=self._generate_commit_hash(content),
            author=author,
            timestamp=datetime.now(),
            message=message,
            changes=self._detect_changes(backup_file, template_file),
        )

        # Save version history
        self._save_version(template_id, version)

        # Update metadata
        self._save_template_metadata(template_id, metadata)
        self._save_index()

        # Git commit if available
        if self.git_backend:
            self._git_commit_template(template_id, f"Update template: {message}")

        logger.info(f"Updated template {template_id} to version {new_version}")
        return version

    def get_template(self, template_id: str) -> Tuple[str, TemplateMetadata]:
        """Get template content and metadata.

        Args:
            template_id: Template ID

        Returns:
            Tuple of (content, metadata)
        """
        if template_id not in self.templates_index:
            raise ValueError(f"Template not found: {template_id}")

        content = self._load_template_content(template_id)
        metadata = self.templates_index[template_id]

        return content, metadata

    def list_templates(
        self, category: Optional[str] = None, tags: Optional[List[str]] = None
    ) -> List[TemplateMetadata]:
        """List templates with optional filtering.

        Args:
            category: Filter by category
            tags: Filter by tags

        Returns:
            List of TemplateMetadata
        """
        templates = list(self.templates_index.values())

        # Filter by category
        if category:
            templates = [t for t in templates if t.category == category]

        # Filter by tags
        if tags:
            tag_set = set(tags)
            templates = [t for t in templates if tag_set.intersection(t.tags)]

        return templates

    def search_templates(self, query: str) -> List[TemplateMetadata]:
        """Search templates by name or description.

        Args:
            query: Search query

        Returns:
            List of matching templates
        """
        query_lower = query.lower()
        matches = []

        for template in self.templates_index.values():
            if (
                query_lower in template.name.lower()
                or query_lower in template.description.lower()
                or any(query_lower in tag.lower() for tag in template.tags)
            ):
                matches.append(template)

        return matches

    def get_template_relationships(
        self, template_id: str
    ) -> List[TemplateRelationship]:
        """Get all relationships for a template.

        Args:
            template_id: Template ID

        Returns:
            List of relationships
        """
        return [r for r in self.relationships if r.parent_template_id == template_id]

    def get_template_versions(self, template_id: str) -> List[TemplateVersion]:
        """Get version history for a template.

        Args:
            template_id: Template ID

        Returns:
            List of template versions
        """
        versions_file = self._get_template_dir(template_id) / "versions.json"

        if not versions_file.exists():
            return []

        with open(versions_file, "r") as f:
            versions_data = json.load(f)

        versions = []
        for v_data in versions_data:
            v_data["timestamp"] = datetime.fromisoformat(v_data["timestamp"])
            versions.append(TemplateVersion(**v_data))

        return versions

    def _generate_template_id(self, name: str, category: str) -> str:
        """Generate unique template ID.

        Args:
            name: Template name
            category: Template category

        Returns:
            Template ID
        """
        # Clean name for ID
        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        clean_category = re.sub(r"[^a-zA-Z0-9_-]", "_", category.lower())

        return f"{clean_category}_{clean_name}"

    def _get_template_dir(self, template_id: str) -> Path:
        """Get directory path for a template.

        Args:
            template_id: Template ID

        Returns:
            Path to template directory
        """
        return self.templates_dir / template_id

    def _load_template_content(self, template_id: str) -> str:
        """Load template content from file.

        Args:
            template_id: Template ID

        Returns:
            Template content
        """
        template_file = self._get_template_dir(template_id) / "template.md"

        if not template_file.exists():
            raise FileNotFoundError(f"Template file not found: {template_file}")

        with open(template_file, "r", encoding="utf-8") as f:
            return f.read()

    def _save_template_metadata(self, template_id: str, metadata: TemplateMetadata):
        """Save template metadata to file.

        Args:
            template_id: Template ID
            metadata: Template metadata
        """
        metadata_file = self._get_template_dir(template_id) / "metadata.json"

        with open(metadata_file, "w") as f:
            json.dump(metadata.to_dict(), f, indent=2)

    def _save_version(self, template_id: str, version: TemplateVersion):
        """Save version record.

        Args:
            template_id: Template ID
            version: Version record
        """
        versions_file = self._get_template_dir(template_id) / "versions.json"

        # Load existing versions
        if versions_file.exists():
            with open(versions_file, "r") as f:
                versions = json.load(f)
        else:
            versions = []

        # Add new version
        versions.append(version.to_dict())

        # Save updated versions
        with open(versions_file, "w") as f:
            json.dump(versions, f, indent=2)

    def _apply_template_modifications(
        self, content: str, fields: List[Dict[str, Any]], modifications: Dict[str, Any]
    ) -> str:
        """Apply field values to template content.

        Args:
            content: Template content
            fields: Template field definitions
            modifications: Field values to apply

        Returns:
            Modified content
        """
        # Simple placeholder replacement
        # In production, would use more sophisticated templating
        for field in fields:
            field_id = field.get("field_id")
            if field_id in modifications:
                placeholder = f"{{{{{field_id}}}}}"
                value = str(modifications[field_id])
                content = content.replace(placeholder, value)

        return content

    def _increment_version(self, current_version: str, increment_type: str) -> str:
        """Increment version number.

        Args:
            current_version: Current version (e.g., "1.2.3")
            increment_type: Type of increment (major, minor, patch)

        Returns:
            New version string
        """
        parts = current_version.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0

        if increment_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif increment_type == "minor":
            minor += 1
            patch = 0
        else:  # patch
            patch += 1

        return f"{major}.{minor}.{patch}"

    def _generate_commit_hash(self, content: str) -> str:
        """Generate hash for content.

        Args:
            content: Content to hash

        Returns:
            Hash string
        """
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def _detect_changes(self, old_file: Path, new_file: Path) -> List[str]:
        """Detect changes between file versions.

        Args:
            old_file: Path to old version
            new_file: Path to new version

        Returns:
            List of change descriptions
        """
        # Simple implementation - in production would use diff algorithm
        changes = []

        if old_file.exists() and new_file.exists():
            old_size = old_file.stat().st_size
            new_size = new_file.stat().st_size

            if new_size > old_size:
                changes.append(f"Content increased by {new_size - old_size} bytes")
            elif new_size < old_size:
                changes.append(f"Content decreased by {old_size - new_size} bytes")
            else:
                changes.append("Content modified")

        return changes

    def _git_commit_template(self, template_id: str, message: str):
        """Commit template changes to git.

        Args:
            template_id: Template ID
            message: Commit message
        """
        if self.git_backend:
            try:
                template_dir = self._get_template_dir(template_id)
                self.git_backend.add(str(template_dir))
                self.git_backend.commit(message)
            except Exception as e:
                logger.warning(f"Failed to commit template to git: {e}")

    def _load_index(self):
        """Load templates index from file."""
        self.templates_index = {}

        if self.index_file.exists():
            with open(self.index_file, "r") as f:
                index_data = json.load(f)

            for template_id, data in index_data.items():
                # Convert datetime strings
                data["created_at"] = datetime.fromisoformat(data["created_at"])
                data["modified_at"] = datetime.fromisoformat(data["modified_at"])
                self.templates_index[template_id] = TemplateMetadata(**data)

    def _save_index(self):
        """Save templates index to file."""
        index_data = {}

        for template_id, metadata in self.templates_index.items():
            index_data[template_id] = metadata.to_dict()

        with open(self.index_file, "w") as f:
            json.dump(index_data, f, indent=2)

    def _load_relationships(self):
        """Load template relationships from file."""
        self.relationships = []

        if self.relationships_file.exists():
            with open(self.relationships_file, "r") as f:
                relationships_data = json.load(f)

            for r_data in relationships_data:
                r_data["created_at"] = datetime.fromisoformat(r_data["created_at"])
                self.relationships.append(TemplateRelationship(**r_data))

    def _save_relationships(self):
        """Save template relationships to file."""
        relationships_data = [r.to_dict() for r in self.relationships]

        with open(self.relationships_file, "w") as f:
            json.dump(relationships_data, f, indent=2)
