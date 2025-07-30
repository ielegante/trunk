"""Template management system for legal document templates."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Template:
    """Represents a legal document template."""

    name: str
    path: Path
    category: str
    variables: List[str]
    metadata: Dict[str, Any]
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


class TemplateManager:
    """Manages legal document templates and variable substitution."""

    def __init__(self, templates_directory: Path):
        """Initialize template manager.

        Args:
            templates_directory: Path to directory containing templates
        """
        self.templates_directory = templates_directory
        self.templates: Dict[str, Template] = {}
        self.template_index_file = templates_directory / "template_index.json"
        self._load_templates()

    def _load_templates(self) -> None:
        """Load templates from the templates directory."""
        if self.template_index_file.exists():
            with open(self.template_index_file, "r") as f:
                index_data = json.load(f)

            for template_data in index_data.get("templates", []):
                template = Template(
                    name=template_data["name"],
                    path=self.templates_directory / template_data["path"],
                    category=template_data["category"],
                    variables=template_data["variables"],
                    metadata=template_data.get("metadata", {}),
                    version=template_data.get("version", "1.0"),
                    created_at=datetime.fromisoformat(
                        template_data.get("created_at", datetime.now().isoformat())
                    ),
                    updated_at=datetime.fromisoformat(
                        template_data.get("updated_at", datetime.now().isoformat())
                    ),
                    is_active=template_data.get("is_active", True),
                )
                self.templates[template.name] = template

    def register_template(self, template: Template) -> None:
        """Register a new template.

        Args:
            template: Template to register
        """
        template.updated_at = datetime.now()
        self.templates[template.name] = template
        self._save_template_index()
        logger.info(f"Registered template: {template.name} v{template.version}")

    def get_template(self, name: str) -> Optional[Template]:
        """Get a template by name.

        Args:
            name: Template name

        Returns:
            Template if found, None otherwise
        """
        return self.templates.get(name)

    def list_templates(
        self, category: Optional[str] = None, include_inactive: bool = False
    ) -> List[Template]:
        """List all templates, optionally filtered by category.

        Args:
            category: Optional category filter
            include_inactive: Whether to include inactive templates

        Returns:
            List of templates
        """
        templates = list(self.templates.values())

        if not include_inactive:
            templates = [t for t in templates if t.is_active]

        if category:
            templates = [t for t in templates if t.category == category]

        return templates

    def instantiate_template(
        self,
        template_name: str,
        variables: Dict[str, Any],
        output_path: Optional[Path] = None,
    ) -> str:
        """Instantiate a template with variable substitution.

        Args:
            template_name: Name of template to instantiate
            variables: Dictionary of variable values
            output_path: Optional output path for generated document

        Returns:
            Generated document content
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")

        # Load template content
        with open(template.path, "r") as f:
            content = f.read()

        # Perform variable substitution
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            content = content.replace(placeholder, str(var_value))

        # Save to output path if specified
        if output_path:
            with open(output_path, "w") as f:
                f.write(content)

        return content

    def validate_template_variables(
        self, template_name: str, variables: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Validate variables for template instantiation.

        Args:
            template_name: Template to validate against
            variables: Variables to validate

        Returns:
            Dictionary with missing and extra variables
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")

        provided_vars = set(variables.keys())
        required_vars = set(template.variables)

        return {
            "missing": list(required_vars - provided_vars),
            "extra": list(provided_vars - required_vars),
        }

    def _save_template_index(self) -> None:
        """Save the template index to disk."""
        index_data = {
            "templates": [
                {
                    "name": template.name,
                    "path": str(template.path.relative_to(self.templates_directory)),
                    "category": template.category,
                    "variables": template.variables,
                    "metadata": template.metadata,
                    "version": template.version,
                    "created_at": template.created_at.isoformat(),
                    "updated_at": template.updated_at.isoformat(),
                    "is_active": template.is_active,
                }
                for template in self.templates.values()
            ]
        }

        with open(self.template_index_file, "w") as f:
            json.dump(index_data, f, indent=2)

    def deprecate_template(self, template_name: str) -> bool:
        """Deprecate a template (mark as inactive).

        Args:
            template_name: Name of template to deprecate

        Returns:
            True if successfully deprecated
        """
        template = self.get_template(template_name)
        if not template:
            return False

        template.is_active = False
        template.updated_at = datetime.now()
        self._save_template_index()

        logger.info(f"Deprecated template: {template_name}")
        return True

    def activate_template(self, template_name: str) -> bool:
        """Activate a deprecated template.

        Args:
            template_name: Name of template to activate

        Returns:
            True if successfully activated
        """
        template = self.get_template(template_name)
        if not template:
            return False

        template.is_active = True
        template.updated_at = datetime.now()
        self._save_template_index()

        logger.info(f"Activated template: {template_name}")
        return True

    def update_template_metadata(
        self, template_name: str, metadata_updates: Dict[str, Any]
    ) -> bool:
        """Update template metadata.

        Args:
            template_name: Name of template to update
            metadata_updates: Metadata updates to apply

        Returns:
            True if successfully updated
        """
        template = self.get_template(template_name)
        if not template:
            return False

        template.metadata.update(metadata_updates)
        template.updated_at = datetime.now()
        self._save_template_index()

        logger.info(f"Updated metadata for template: {template_name}")
        return True

    def get_template_statistics(self) -> Dict[str, Any]:
        """Get template collection statistics.

        Returns:
            Statistics about template collection
        """
        templates = list(self.templates.values())
        active_templates = [t for t in templates if t.is_active]

        categories = {}
        for template in active_templates:
            category = template.category
            if category not in categories:
                categories[category] = 0
            categories[category] += 1

        return {
            "total_templates": len(templates),
            "active_templates": len(active_templates),
            "inactive_templates": len(templates) - len(active_templates),
            "categories": categories,
            "latest_update": (
                max([t.updated_at for t in templates]).isoformat()
                if templates
                else None
            ),
        }
