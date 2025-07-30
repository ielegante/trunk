import json
import logging
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from app.git_ops.repository import GitOperations
from app.security.sanitizer import ContentSanitizer, ContentType, SanitizationLevel

logger = logging.getLogger(__name__)


class TemplateType(Enum):
    """Types of repository templates"""

    LEGAL_CONTRACT = "legal_contract"
    CORPORATE_POLICY = "corporate_policy"
    COMPLIANCE_DOC = "compliance_doc"
    LEGAL_BRIEF = "legal_brie"
    MEMO = "memo"
    AGREEMENT = "agreement"
    CUSTOM = "custom"


class TemplateStatus(Enum):
    """Status of template repositories"""

    ACTIVE = "active"
    DRAFT = "draft"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


@dataclass
class TemplateMetadata:
    """Metadata for repository templates"""

    id: str
    name: str
    description: str
    template_type: TemplateType
    status: TemplateStatus
    version: str
    author: str
    created_at: datetime
    updated_at: datetime
    tags: List[str]
    category: str
    language: str = "en"
    jurisdiction: Optional[str] = None
    practice_area: Optional[str] = None
    difficulty_level: str = "intermediate"
    estimated_time: Optional[str] = None


@dataclass
class TemplateStructure:
    """Structure definition for templates"""

    directories: List[str]
    required_files: List[str]
    optional_files: List[str]
    file_templates: Dict[str, str]
    placeholders: Dict[str, str]
    validation_rules: Dict[str, Any]


class RepositoryTemplateManager:
    """Manager for repository templates with security and sanitization"""

    def __init__(self, templates_base_path: str = "./repository_templates"):
        self.templates_path = Path(templates_base_path)
        self.templates_path.mkdir(exist_ok=True)
        self.git_ops = GitOperations()
        self.sanitizer = ContentSanitizer()

        # Initialize template registry
        self.registry_file = self.templates_path / "template_registry.json"
        self.template_registry = self._load_template_registry()

    def _load_template_registry(self) -> Dict[str, TemplateMetadata]:
        """Load template registry from disk"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    registry_data = json.load(f)

                registry = {}
                for template_id, data in registry_data.items():
                    # Convert datetime strings back to datetime objects
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                    data["template_type"] = TemplateType(data["template_type"])
                    data["status"] = TemplateStatus(data["status"])

                    registry[template_id] = TemplateMetadata(**data)

                return registry
            except Exception as e:
                logger.warning(f"Failed to load template registry: {str(e)}")

        return {}

    def _save_template_registry(self):
        """Save template registry to disk"""
        try:
            registry_data = {}
            for template_id, metadata in self.template_registry.items():
                data = asdict(metadata)
                # Convert datetime objects to strings
                data["created_at"] = metadata.created_at.isoformat()
                data["updated_at"] = metadata.updated_at.isoformat()
                data["template_type"] = metadata.template_type.value
                data["status"] = metadata.status.value

                registry_data[template_id] = data

            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(registry_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save template registry: {str(e)}")

    def create_template(
        self,
        name: str,
        description: str,
        template_type: TemplateType,
        author: str,
        structure: TemplateStructure,
        content_files: Dict[str, str],
        metadata_override: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Create a new repository template"""

        try:
            # Generate template ID
            template_id = str(uuid.uuid4())

            # Sanitize inputs
            name = self.sanitizer.sanitize_content(
                name, ContentType.PLAIN_TEXT, SanitizationLevel.MODERATE
            ).sanitized_content
            description = self.sanitizer.sanitize_content(
                description, ContentType.PLAIN_TEXT, SanitizationLevel.MODERATE
            ).sanitized_content

            # Create template metadata
            metadata = TemplateMetadata(
                id=template_id,
                name=name,
                description=description,
                template_type=template_type,
                status=TemplateStatus.DRAFT,
                version="1.0.0",
                author=author,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                tags=metadata_override.get("tags", []) if metadata_override else [],
                category=(
                    metadata_override.get("category", "general")
                    if metadata_override
                    else "general"
                ),
                jurisdiction=(
                    metadata_override.get("jurisdiction") if metadata_override else None
                ),
                practice_area=(
                    metadata_override.get("practice_area")
                    if metadata_override
                    else None
                ),
            )

            # Create template directory
            template_dir = self.templates_path / template_id
            template_dir.mkdir(exist_ok=True)

            # Create directory structure
            for directory in structure.directories:
                safe_dir = self.sanitizer.sanitize_content(
                    directory, ContentType.FILENAME
                ).sanitized_content
                (template_dir / safe_dir).mkdir(parents=True, exist_ok=True)

            # Create and sanitize content files
            sanitized_files = {}
            for file_path, content in content_files.items():
                safe_path = self.sanitizer.sanitize_content(
                    file_path, ContentType.FILENAME
                ).sanitized_content

                # Determine content type for sanitization
                if file_path.endswith((".md", ".markdown")):
                    content_type = ContentType.MARKDOWN
                elif file_path.endswith((".html", ".htm")):
                    content_type = ContentType.HTML
                else:
                    content_type = ContentType.PLAIN_TEXT

                sanitized_result = self.sanitizer.sanitize_content(
                    content, content_type, SanitizationLevel.MODERATE
                )

                if not sanitized_result.is_safe:
                    logger.warning(
                        f"Content safety issues in {file_path}: {sanitized_result.issues_found}"
                    )

                sanitized_files[safe_path] = sanitized_result.sanitized_content

                # Write file
                full_path = template_dir / safe_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(sanitized_result.sanitized_content)

            # Save template structure
            structure_file = template_dir / "template_structure.json"
            structure_data = {
                "directories": structure.directories,
                "required_files": structure.required_files,
                "optional_files": structure.optional_files,
                "file_templates": structure.file_templates,
                "placeholders": structure.placeholders,
                "validation_rules": structure.validation_rules,
            }

            with open(structure_file, "w", encoding="utf-8") as f:
                json.dump(structure_data, f, indent=2)

            # Save metadata
            metadata_file = template_dir / "template_metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                metadata_data = asdict(metadata)
                metadata_data["created_at"] = metadata.created_at.isoformat()
                metadata_data["updated_at"] = metadata.updated_at.isoformat()
                metadata_data["template_type"] = metadata.template_type.value
                metadata_data["status"] = metadata.status.value
                json.dump(metadata_data, f, indent=2)

            # Add to registry
            self.template_registry[template_id] = metadata
            self._save_template_registry()

            return {
                "success": True,
                "template_id": template_id,
                "metadata": asdict(metadata),
                "sanitized_files": list(sanitized_files.keys()),
                "template_path": str(template_dir),
            }

        except Exception as e:
            logger.error(f"Failed to create template: {str(e)}")
            return {"success": False, "error": str(e)}

    def instantiate_template(
        self,
        template_id: str,
        repo_name: str,
        user_id: str,
        placeholder_values: Dict[str, str],
        custom_structure: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Instantiate a template as a new repository"""

        try:
            # Validate template exists
            if template_id not in self.template_registry:
                return {"success": False, "error": f"Template {template_id} not found"}

            metadata = self.template_registry[template_id]

            # Check template status
            if metadata.status == TemplateStatus.DEPRECATED:
                return {
                    "success": False,
                    "error": "Template is deprecated and cannot be instantiated",
                }

            # Sanitize inputs
            repo_name = self.sanitizer.sanitize_content(
                repo_name, ContentType.FILENAME
            ).sanitized_content

            # Sanitize placeholder values
            sanitized_placeholders = {}
            for key, value in placeholder_values.items():
                safe_key = self.sanitizer.sanitize_content(
                    key, ContentType.PLAIN_TEXT
                ).sanitized_content
                safe_value = self.sanitizer.sanitize_content(
                    value, ContentType.PLAIN_TEXT, SanitizationLevel.MODERATE
                ).sanitized_content
                sanitized_placeholders[safe_key] = safe_value

            # Create repository using git operations
            repo_result = self.git_ops.clone_repository(
                "", repo_name, user_id
            )  # Create empty repo
            if not repo_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to create repository: {repo_result.get('error', 'Unknown error')}",
                }

            # Get template directory
            template_dir = self.templates_path / template_id

            # Load template structure
            structure_file = template_dir / "template_structure.json"
            if structure_file.exists():
                with open(structure_file, "r", encoding="utf-8") as f:
                    structure_data = json.load(f)
                structure = TemplateStructure(**structure_data)
            else:
                return {"success": False, "error": "Template structure file not found"}

            # Get repository path
            repo_path = self.git_ops.base_path / user_id / repo_name

            # Copy and process template files
            processed_files = []

            for file_path in structure.required_files + structure.optional_files:
                template_file = template_dir / file_path

                if template_file.exists():
                    # Read template content
                    with open(template_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Replace placeholders
                    processed_content = self._replace_placeholders(
                        content, sanitized_placeholders
                    )

                    # Sanitize processed content
                    if file_path.endswith((".md", ".markdown")):
                        content_type = ContentType.MARKDOWN
                    elif file_path.endswith((".html", ".htm")):
                        content_type = ContentType.HTML
                    else:
                        content_type = ContentType.PLAIN_TEXT

                    sanitized_result = self.sanitizer.sanitize_content(
                        processed_content, content_type
                    )

                    # Write to repository
                    repo_file = repo_path / file_path
                    repo_file.parent.mkdir(parents=True, exist_ok=True)

                    with open(repo_file, "w", encoding="utf-8") as f:
                        f.write(sanitized_result.sanitized_content)

                    processed_files.append(file_path)

            # Create directories
            for directory in structure.directories:
                (repo_path / directory).mkdir(parents=True, exist_ok=True)

            # Create template metadata in repository
            template_info = {
                "template_id": template_id,
                "template_name": metadata.name,
                "template_version": metadata.version,
                "instantiated_at": datetime.utcnow().isoformat(),
                "placeholder_values": sanitized_placeholders,
                "processed_files": processed_files,
            }

            metadata_dir = repo_path / ".trunk" / "template"
            metadata_dir.mkdir(parents=True, exist_ok=True)

            with open(metadata_dir / "template_info.json", "w", encoding="utf-8") as f:
                json.dump(template_info, f, indent=2)

            # Initial commit
            commit_message = f"Initialize repository from template: {metadata.name}\n\nTemplate ID: {template_id}\nTemplate Version: {metadata.version}"

            commit_result = self.git_ops.commit_changes(
                repo_name, user_id, commit_message
            )

            return {
                "success": True,
                "repository_name": repo_name,
                "template_metadata": asdict(metadata),
                "processed_files": processed_files,
                "placeholder_values": sanitized_placeholders,
                "commit_result": commit_result,
            }

        except Exception as e:
            logger.error(f"Failed to instantiate template: {str(e)}")
            return {"success": False, "error": str(e)}

    def _replace_placeholders(
        self, content: str, placeholder_values: Dict[str, str]
    ) -> str:
        """Replace placeholders in content with provided values"""
        processed_content = content

        for placeholder, value in placeholder_values.items():
            # Support multiple placeholder formats
            patterns = [
                f"{{{{{placeholder}}}}}",  # {{placeholder}}
                f"${{{placeholder}}}",  # ${placeholder}
                f"[{placeholder}]",  # [placeholder]
                f"__{placeholder}__",  # __placeholder__
            ]

            for pattern in patterns:
                processed_content = processed_content.replace(pattern, value)

        return processed_content

    def list_templates(
        self,
        template_type: Optional[TemplateType] = None,
        status: Optional[TemplateStatus] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List available templates with filtering"""

        filtered_templates = {}

        for template_id, metadata in self.template_registry.items():
            # Apply filters
            if template_type and metadata.template_type != template_type:
                continue

            if status and metadata.status != status:
                continue

            if category and metadata.category != category:
                continue

            filtered_templates[template_id] = {
                "id": metadata.id,
                "name": metadata.name,
                "description": metadata.description,
                "type": metadata.template_type.value,
                "status": metadata.status.value,
                "version": metadata.version,
                "author": metadata.author,
                "created_at": metadata.created_at.isoformat(),
                "updated_at": metadata.updated_at.isoformat(),
                "tags": metadata.tags,
                "category": metadata.category,
                "practice_area": metadata.practice_area,
                "jurisdiction": metadata.jurisdiction,
            }

        return {
            "success": True,
            "templates": filtered_templates,
            "total_count": len(filtered_templates),
        }

    def get_template_details(self, template_id: str) -> Dict[str, Any]:
        """Get detailed information about a template"""

        if template_id not in self.template_registry:
            return {"success": False, "error": "Template not found"}

        try:
            metadata = self.template_registry[template_id]
            template_dir = self.templates_path / template_id

            # Load structure
            structure_file = template_dir / "template_structure.json"
            structure_data = {}
            if structure_file.exists():
                with open(structure_file, "r", encoding="utf-8") as f:
                    structure_data = json.load(f)

            # Get file list
            template_files = []
            if template_dir.exists():
                for file_path in template_dir.rglob("*"):
                    if file_path.is_file() and not file_path.name.startswith("."):
                        relative_path = file_path.relative_to(template_dir)
                        template_files.append(str(relative_path))

            return {
                "success": True,
                "metadata": asdict(metadata),
                "structure": structure_data,
                "files": template_files,
                "template_path": str(template_dir),
            }

        except Exception as e:
            logger.error(f"Failed to get template details: {str(e)}")
            return {"success": False, "error": str(e)}

    def update_template_status(
        self, template_id: str, new_status: TemplateStatus
    ) -> Dict[str, Any]:
        """Update template status"""

        if template_id not in self.template_registry:
            return {"success": False, "error": "Template not found"}

        try:
            self.template_registry[template_id].status = new_status
            self.template_registry[template_id].updated_at = datetime.utcnow()

            self._save_template_registry()

            return {
                "success": True,
                "template_id": template_id,
                "new_status": new_status.value,
            }

        except Exception as e:
            logger.error(f"Failed to update template status: {str(e)}")
            return {"success": False, "error": str(e)}

    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """Delete a template (with safety checks)"""

        if template_id not in self.template_registry:
            return {"success": False, "error": "Template not found"}

        try:
            metadata = self.template_registry[template_id]

            # Safety check - only allow deletion of draft templates
            if metadata.status not in [TemplateStatus.DRAFT, TemplateStatus.DEPRECATED]:
                return {
                    "success": False,
                    "error": "Only draft or deprecated templates can be deleted",
                }

            # Remove template directory
            template_dir = self.templates_path / template_id
            if template_dir.exists():
                shutil.rmtree(template_dir)

            # Remove from registry
            del self.template_registry[template_id]
            self._save_template_registry()

            return {
                "success": True,
                "template_id": template_id,
                "message": f"Template '{metadata.name}' deleted successfully",
            }

        except Exception as e:
            logger.error(f"Failed to delete template: {str(e)}")
            return {"success": False, "error": str(e)}

    def validate_template(self, template_id: str) -> Dict[str, Any]:
        """Validate template structure and content"""

        if template_id not in self.template_registry:
            return {"success": False, "error": "Template not found"}

        try:
            template_dir = self.templates_path / template_id
            validation_results = {
                "is_valid": True,
                "warnings": [],
                "errors": [],
                "file_validations": [],
            }

            # Check if template directory exists
            if not template_dir.exists():
                validation_results["is_valid"] = False
                validation_results["errors"].append("Template directory not found")
                return {"success": True, "validation": validation_results}

            # Load and validate structure
            structure_file = template_dir / "template_structure.json"
            if not structure_file.exists():
                validation_results["is_valid"] = False
                validation_results["errors"].append("Template structure file missing")
            else:
                with open(structure_file, "r", encoding="utf-8") as f:
                    structure_data = json.load(f)

                structure = TemplateStructure(**structure_data)

                # Validate required files exist
                for required_file in structure.required_files:
                    file_path = template_dir / required_file
                    if not file_path.exists():
                        validation_results["is_valid"] = False
                        validation_results["errors"].append(
                            f"Required file missing: {required_file}"
                        )
                    else:
                        # Validate file content
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        # Determine content type
                        if required_file.endswith((".md", ".markdown")):
                            content_type = ContentType.MARKDOWN
                        elif required_file.endswith((".html", ".htm")):
                            content_type = ContentType.HTML
                        else:
                            content_type = ContentType.PLAIN_TEXT

                        # Sanitize and check
                        sanitized_result = self.sanitizer.sanitize_content(
                            content, content_type
                        )

                        file_validation = {
                            "file": required_file,
                            "is_safe": sanitized_result.is_safe,
                            "security_score": sanitized_result.security_score,
                            "issues": sanitized_result.issues_found,
                        }

                        validation_results["file_validations"].append(file_validation)

                        if not sanitized_result.is_safe:
                            validation_results["warnings"].append(
                                f"Security issues in {required_file}: {', '.join(sanitized_result.issues_found)}"
                            )

            return {"success": True, "validation": validation_results}

        except Exception as e:
            logger.error(f"Failed to validate template: {str(e)}")
            return {"success": False, "error": str(e)}
