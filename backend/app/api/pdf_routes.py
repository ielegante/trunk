import logging
from typing import Any, Dict, Optional

from app.api.auth_routes import get_current_user
from app.pdf.pdf_extractor import PDFExtractor, PDFProcessor
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


# Request/Response Models
class PDFExtractionRequest(BaseModel):
    file_path: str = Field(..., description="Path to PDF file in Google Drive")
    repository_id: str = Field(..., description="Repository ID for the PDF")
    extract_full_text: bool = Field(True, description="Extract full text content")
    create_git_tracking: bool = Field(
        True, description="Create git-trackable representation"
    )


class PDFMetadataResponse(BaseModel):
    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    creator: Optional[str]
    producer: Optional[str]
    creation_date: Optional[str]
    modification_date: Optional[str]
    page_count: int
    file_size: int
    content_hash: str


class PDFPageResponse(BaseModel):
    page_number: int
    text_length: int
    has_images: bool
    has_tables: bool


class PDFExtractionResponse(BaseModel):
    success: bool
    extraction_method: str
    extraction_timestamp: str
    metadata: PDFMetadataResponse
    pages: list[PDFPageResponse]
    text_length: int
    error_message: Optional[str] = None


class PDFGitTrackingResponse(BaseModel):
    file_path: str
    content_type: str
    git_data: Dict[str, Any]
    markdown_summary: str


# Dependency to get PDF services
def get_pdf_extractor() -> PDFExtractor:
    return PDFExtractor()


def get_pdf_processor() -> PDFProcessor:
    extractor = get_pdf_extractor()
    return PDFProcessor(extractor)


# PDF Processing Endpoints


@router.post("/extract", response_model=PDFExtractionResponse)
async def extract_pdf_content(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    pdf_extractor: PDFExtractor = Depends(get_pdf_extractor),
):
    """
    Extract text and metadata from uploaded PDF file
    """
    try:
        # Validate file type
        if not file.content_type == "application/pd":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported",
            )

        # Read file content
        file_content = await file.read()

        # Extract content
        pdf_content = pdf_extractor.extract_from_bytes(file_content, file.filename)

        # Convert to response format
        metadata_response = PDFMetadataResponse(
            title=pdf_content.metadata.title,
            author=pdf_content.metadata.author,
            subject=pdf_content.metadata.subject,
            creator=pdf_content.metadata.creator,
            producer=pdf_content.metadata.producer,
            creation_date=(
                pdf_content.metadata.creation_date.isoformat()
                if pdf_content.metadata.creation_date
                else None
            ),
            modification_date=(
                pdf_content.metadata.modification_date.isoformat()
                if pdf_content.metadata.modification_date
                else None
            ),
            page_count=pdf_content.metadata.page_count,
            file_size=pdf_content.metadata.file_size,
            content_hash=pdf_content.metadata.content_hash or "",
        )

        pages_response = [
            PDFPageResponse(
                page_number=page.page_number,
                text_length=page.text_length,
                has_images=page.has_images,
                has_tables=page.has_tables,
            )
            for page in pdf_content.pages
        ]

        response = PDFExtractionResponse(
            success=pdf_content.success,
            extraction_method=pdf_content.extraction_method,
            extraction_timestamp=pdf_content.extraction_timestamp.isoformat(),
            metadata=metadata_response,
            pages=pages_response,
            text_length=pdf_content.text_length,
            error_message=pdf_content.error_message,
        )

        logger.info(
            f"PDF extraction completed for {file.filename} by {current_user.get('name')}"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF extraction failed for {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during PDF extraction",
        )


@router.post("/extract-text", response_model=Dict[str, Any])
async def extract_pdf_text_only(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    pdf_extractor: PDFExtractor = Depends(get_pdf_extractor),
):
    """
    Extract only text content from PDF (lighter endpoint)
    """
    try:
        # Validate file type
        if not file.content_type == "application/pd":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported",
            )

        # Read file content
        file_content = await file.read()

        # Extract content
        pdf_content = pdf_extractor.extract_from_bytes(file_content, file.filename)

        result = {
            "filename": file.filename,
            "success": pdf_content.success,
            "text_content": pdf_content.full_text if pdf_content.success else "",
            "text_length": pdf_content.text_length,
            "page_count": pdf_content.metadata.page_count,
            "extraction_method": pdf_content.extraction_method,
            "error_message": pdf_content.error_message,
        }

        logger.info(f"PDF text extraction completed for {file.filename}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF text extraction failed for {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during PDF text extraction",
        )


@router.post("/process-for-git", response_model=PDFGitTrackingResponse)
async def process_pdf_for_git_tracking(
    file: UploadFile = File(...),
    file_path: str = Form(..., description="Path in repository"),
    current_user=Depends(get_current_user),
    pdf_processor: PDFProcessor = Depends(get_pdf_processor),
):
    """
    Process PDF for git tracking with markdown summary
    """
    try:
        # Validate file type
        if not file.content_type == "application/pd":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported",
            )

        # Read file content
        file_content = await file.read()

        # Extract content
        pdf_content = pdf_processor.extractor.extract_from_bytes(
            file_content, file.filename
        )

        # Process for git tracking
        git_data = pdf_processor.process_for_git_tracking(pdf_content, file_path)

        # Create markdown summary
        markdown_summary = pdf_processor.create_markdown_summary(pdf_content, file_path)

        response = PDFGitTrackingResponse(
            file_path=file_path,
            content_type="pd",
            git_data=git_data,
            markdown_summary=markdown_summary,
        )

        logger.info(f"PDF git processing completed for {file.filename} at {file_path}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF git processing failed for {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during PDF git processing",
        )


@router.get("/health")
async def pdf_service_health():
    """
    Check PDF service health
    """
    try:
        # Test basic PDF extraction functionality
        extractor = get_pdf_extractor()

        # Create a minimal test PDF content
        test_pdf = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n174\n%%EOF"

        result = extractor.extract_from_bytes(test_pdf, "test.pdf")

        return {
            "status": "healthy",
            "service": "pdf-extraction",
            "test_extraction": result.success,
            "extraction_method": result.extraction_method,
            "max_file_size_mb": extractor.max_file_size / (1024 * 1024),
        }

    except Exception as e:
        logger.error(f"PDF service health check failed: {e}")
        return {"status": "unhealthy", "service": "pdf-extraction", "error": str(e)}


@router.get("/info")
async def pdf_service_info():
    """
    Get PDF service information and capabilities
    """
    return {
        "service": "pdf-extraction",
        "supported_formats": ["application/pd"],
        "extraction_methods": [
            {
                "name": "pdfplumber",
                "description": "Primary method with table and image detection",
                "capabilities": ["text", "tables", "images", "metadata"],
            },
            {
                "name": "pypdf2",
                "description": "Fallback method for problematic PDFs",
                "capabilities": ["text", "metadata"],
            },
            {
                "name": "metadata_only",
                "description": "Last resort when text extraction fails",
                "capabilities": ["metadata"],
            },
        ],
        "max_file_size_mb": 100,
        "features": [
            "Text extraction",
            "Metadata extraction",
            "Page-by-page processing",
            "Table detection",
            "Image detection",
            "Git tracking integration",
            "Markdown summary generation",
        ],
    }
