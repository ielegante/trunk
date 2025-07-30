# import json  # TODO: Remove if not needed
from typing import Any, Dict, Optional

from app.api.auth_routes import get_current_user_id
from app.security.access_control import Permission, Role, access_control
from app.security.sanitizer import ContentSanitizer, ContentType, SanitizationLevel
from app.templates.repository_manager import (
    RepositoryTemplateManager,
    TemplateStatus,
    TemplateStructure,
    TemplateType,
)
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/templates", tags=["repository templates"])
template_manager = RepositoryTemplateManager()
sanitizer = ContentSanitizer()


class CreateTemplateRequest(BaseModel):
    name: str
    description: str
    template_type: str
    structure: Dict[str, Any]
    content_files: Dict[str, str]
    metadata: Optional[Dict[str, Any]] = None


class InstantiateTemplateRequest(BaseModel):
    template_id: str
    repo_name: str
    placeholder_values: Dict[str, str]
    custom_structure: Optional[Dict[str, Any]] = None


class UpdateTemplateStatusRequest(BaseModel):
    template_id: str
    new_status: str


@router.post("/create")
@access_control.rate_limit("upload")
async def create_template(
    request: CreateTemplateRequest,
    user_id: str = Depends(get_current_user_id),
    http_request: Request = None,
):
    """Create a new repository template"""

    # Check permissions
    if not access_control.check_permission(
        Role.POWER_USER, Permission.CREATE_TEMPLATES
    ):
        # Get user role from request for proper permission check
        user_role = access_control._get_user_role_from_request(http_request)
        if not access_control.check_permission(user_role, Permission.CREATE_TEMPLATES):
            raise HTTPException(
                status_code=403, detail="Permission denied: CREATE_TEMPLATES required"
            )

    try:
        # Validate and sanitize inputs
        sanitized_name = sanitizer.sanitize_content(
            request.name, ContentType.PLAIN_TEXT, SanitizationLevel.MODERATE
        )
        if not sanitized_name.is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"Template name contains unsafe content: {sanitized_name.issues_found}",
            )

        sanitized_description = sanitizer.sanitize_content(
            request.description, ContentType.PLAIN_TEXT, SanitizationLevel.MODERATE
        )
        if not sanitized_description.is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"Description contains unsafe content: {sanitized_description.issues_found}",
            )

        # Validate template type
        try:
            template_type = TemplateType(request.template_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid template type: {request.template_type}",
            )

        # Validate and sanitize content files
        sanitized_files = {}
        for file_path, content in request.content_files.items():
            # Sanitize file path
            safe_path = sanitizer.sanitize_content(
                file_path, ContentType.FILENAME
            ).sanitized_content

            # Determine content type and sanitize
            if file_path.endswith((".md", ".markdown")):
                content_type = ContentType.MARKDOWN
            elif file_path.endswith((".html", ".htm")):
                content_type = ContentType.HTML
            else:
                content_type = ContentType.PLAIN_TEXT

            sanitized_content = sanitizer.sanitize_content(
                content, content_type, SanitizationLevel.MODERATE
            )

            if not sanitized_content.is_safe:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsafe content in {file_path}: {sanitized_content.issues_found}",
                )

            sanitized_files[safe_path] = sanitized_content.sanitized_content

        # Create template structure
        structure = TemplateStructure(
            directories=request.structure.get("directories", []),
            required_files=request.structure.get("required_files", []),
            optional_files=request.structure.get("optional_files", []),
            file_templates=request.structure.get("file_templates", {}),
            placeholders=request.structure.get("placeholders", {}),
            validation_rules=request.structure.get("validation_rules", {}),
        )

        # Create template
        result = template_manager.create_template(
            name=sanitized_name.sanitized_content,
            description=sanitized_description.sanitized_content,
            template_type=template_type,
            author=user_id,
            structure=structure,
            content_files=sanitized_files,
            metadata_override=request.metadata,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Template creation failed: {str(e)}"
        )


@router.post("/instantiate")
@access_control.rate_limit("default")
async def instantiate_template(
    request: InstantiateTemplateRequest,
    user_id: str = Depends(get_current_user_id),
    http_request: Request = None,
):
    """Instantiate a template as a new repository"""

    # Check permissions
    user_role = access_control._get_user_role_from_request(http_request)
    if not access_control.check_permission(user_role, Permission.INSTANTIATE_TEMPLATES):
        raise HTTPException(
            status_code=403, detail="Permission denied: INSTANTIATE_TEMPLATES required"
        )

    try:
        # Sanitize inputs
        sanitized_repo_name = sanitizer.sanitize_content(
            request.repo_name, ContentType.FILENAME, SanitizationLevel.MODERATE
        )
        if not sanitized_repo_name.is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"Repository name contains unsafe content: {sanitized_repo_name.issues_found}",
            )

        # Sanitize placeholder values
        sanitized_placeholders = {}
        for key, value in request.placeholder_values.items():
            safe_key = sanitizer.sanitize_content(
                key, ContentType.PLAIN_TEXT
            ).sanitized_content
            safe_value = sanitizer.sanitize_content(
                value, ContentType.PLAIN_TEXT, SanitizationLevel.MODERATE
            ).sanitized_content
            sanitized_placeholders[safe_key] = safe_value

        # Instantiate template
        result = template_manager.instantiate_template(
            template_id=request.template_id,
            repo_name=sanitized_repo_name.sanitized_content,
            user_id=user_id,
            placeholder_values=sanitized_placeholders,
            custom_structure=request.custom_structure,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Template instantiation failed: {str(e)}"
        )


@router.get("/list")
async def list_templates(
    template_type: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
):
    """List available templates with filtering"""

    try:
        # Convert string parameters to enums
        type_filter = TemplateType(template_type) if template_type else None
        status_filter = TemplateStatus(status) if status else None

        result = template_manager.list_templates(
            template_type=type_filter, status=status_filter, category=category
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid filter parameter: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list templates: {str(e)}"
        )


@router.get("/details/{template_id}")
async def get_template_details(
    template_id: str, user_id: str = Depends(get_current_user_id)
):
    """Get detailed information about a template"""

    try:
        result = template_manager.get_template_details(template_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get template details: {str(e)}"
        )


@router.put("/status")
async def update_template_status(
    request: UpdateTemplateStatusRequest,
    user_id: str = Depends(get_current_user_id),
    http_request: Request = None,
):
    """Update template status"""

    # Check permissions
    user_role = access_control._get_user_role_from_request(http_request)
    if not access_control.check_permission(user_role, Permission.MODIFY_TEMPLATES):
        raise HTTPException(
            status_code=403, detail="Permission denied: MODIFY_TEMPLATES required"
        )

    try:
        # Validate status
        try:
            new_status = TemplateStatus(request.new_status)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {request.new_status}"
            )

        result = template_manager.update_template_status(
            request.template_id, new_status
        )

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update template status: {str(e)}"
        )


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user_id),
    http_request: Request = None,
):
    """Delete a template"""

    # Check permissions
    user_role = access_control._get_user_role_from_request(http_request)
    if not access_control.check_permission(user_role, Permission.DELETE_TEMPLATES):
        raise HTTPException(
            status_code=403, detail="Permission denied: DELETE_TEMPLATES required"
        )

    try:
        result = template_manager.delete_template(template_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete template: {str(e)}"
        )


@router.get("/validate/{template_id}")
async def validate_template(
    template_id: str, user_id: str = Depends(get_current_user_id)
):
    """Validate template structure and content"""

    try:
        result = template_manager.validate_template(template_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Template validation failed: {str(e)}"
        )


@router.post("/upload-template")
@access_control.rate_limit("upload")
async def upload_template_file(
    file: UploadFile = File(...),
    template_name: str = Form(...),
    template_description: str = Form(...),
    template_type: str = Form(...),
    user_id: str = Depends(get_current_user_id),
    http_request: Request = None,
):
    """Upload a template file (e.g., ZIP archive)"""

    # Check permissions
    user_role = access_control._get_user_role_from_request(http_request)
    if not access_control.check_permission(user_role, Permission.CREATE_TEMPLATES):
        raise HTTPException(
            status_code=403, detail="Permission denied: CREATE_TEMPLATES required"
        )

    try:
        # Validate file upload
        file_content = await file.read()

        upload_validation = access_control.validate_file_upload(
            file.filename, len(file_content), file.content_type
        )

        if not upload_validation["allowed"]:
            raise HTTPException(
                status_code=400,
                detail=f"File upload validation failed: {'; '.join(upload_validation['issues'])}",
            )

        # Additional security validation
        file_validation = sanitizer.validate_file_upload(
            file.filename,
            file_content,
            allowed_extensions=[".zip", ".tar.gz", ".json"],
            max_size=50 * 1024 * 1024,  # 50MB
        )

        if not file_validation["is_valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"File security validation failed: {'; '.join(file_validation['issues'])}",
            )

        # TODO: Implement template file processing
        # This would involve extracting the archive and creating the template

        return {
            "success": True,
            "message": "Template file uploaded successfully",
            "filename": file_validation["sanitized_filename"],
            "file_info": file_validation["file_info"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template upload failed: {str(e)}")


@router.post("/sanitize-content")
async def sanitize_template_content(
    content: str = Form(...),
    content_type: str = Form("plain_text"),
    sanitization_level: str = Form("moderate"),
    user_id: str = Depends(get_current_user_id),
):
    """Sanitize content for template use"""

    try:
        # Convert string parameters to enums
        try:
            content_type_enum = ContentType(content_type)
            sanitization_level_enum = SanitizationLevel(sanitization_level)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid parameter: {str(e)}")

        # Sanitize content
        result = sanitizer.sanitize_content(
            content, content_type_enum, sanitization_level_enum
        )

        return {
            "success": True,
            "sanitized_content": result.sanitized_content,
            "original_content": result.original_content,
            "issues_found": result.issues_found,
            "changes_made": result.changes_made,
            "security_score": result.security_score,
            "is_safe": result.is_safe,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Content sanitization failed: {str(e)}"
        )


@router.get("/types")
async def get_template_types(user_id: str = Depends(get_current_user_id)):
    """Get available template types"""

    return {
        "success": True,
        "template_types": [
            {
                "value": template_type.value,
                "name": template_type.value.replace("_", " ").title(),
                "description": f"Template for {template_type.value.replace('_', ' ')}",
            }
            for template_type in TemplateType
        ],
    }


@router.get("/statuses")
async def get_template_statuses(user_id: str = Depends(get_current_user_id)):
    """Get available template statuses"""

    return {
        "success": True,
        "template_statuses": [
            {
                "value": status.value,
                "name": status.value.title(),
                "description": f"Template is {status.value}",
            }
            for status in TemplateStatus
        ],
    }
