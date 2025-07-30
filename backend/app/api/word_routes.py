import io
import json
from typing import Optional

from app.api.auth_routes import get_current_user_id
from app.word_processing.word_service import WordProcessingService
from app.word_processing.xml_service import WordXMLService
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/word", tags=["word processing"])
word_service = WordProcessingService()
xml_service = WordXMLService()


class WordToGitRequest(BaseModel):
    repo_name: str
    file_path: str
    conversion_format: str = "markdown"


class CompareDocumentsRequest(BaseModel):
    comparison_type: str = "basic"


class MarkdownToWordRequest(BaseModel):
    markdown_content: str
    filename: str = "document.docx"


@router.post("/upload-process")
async def upload_and_process_word_document(
    file: UploadFile = File(...),
    processing_options: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id),
):
    """Upload and process a Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Parse processing options
        options = {}
        if processing_options:
            try:
                options = json.loads(processing_options)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Invalid processing options JSON"
                )

        # Process document
        result = await word_service.process_word_document(
            file_content, file.filename, user_id, options
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/sync-to-git")
async def sync_word_to_git(
    file: UploadFile = File(...),
    repo_name: str = Form(...),
    file_path: str = Form(...),
    conversion_format: str = Form("markdown"),
    user_id: str = Depends(get_current_user_id),
):
    """Sync Word document to git repository"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Sync to git
        result = await word_service.sync_word_to_git(
            file_content,
            file.filename,
            repo_name,
            user_id,
            file_path,
            conversion_format,
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/convert-to-markdown")
async def convert_word_to_markdown(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Convert Word document to Markdown"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Convert to markdown
        processor = word_service.docx_processor
        markdown_content = processor.convert_bytes_to_markdown(file_content)

        return {
            "success": True,
            "filename": file.filename,
            "markdown_content": markdown_content,
            "character_count": len(markdown_content),
            "word_count": len(markdown_content.split()),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.post("/convert-to-text")
async def convert_word_to_text(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Convert Word document to plain text"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Load and convert document
        processor = word_service.docx_processor
        document = processor.load_document_from_bytes(file_content)
        text_content = processor.extract_text_content(document)

        return {
            "success": True,
            "filename": file.filename,
            "text_content": text_content,
            "character_count": len(text_content),
            "word_count": len(text_content.split()),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.post("/create-from-markdown")
async def create_word_from_markdown(
    request: MarkdownToWordRequest, user_id: str = Depends(get_current_user_id)
):
    """Create Word document from Markdown content"""

    try:
        # Create Word document
        docx_bytes = await word_service.create_word_from_markdown(
            request.markdown_content, request.filename
        )

        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={request.filename}"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Document creation failed: {str(e)}"
        )


@router.post("/compare")
async def compare_word_documents(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    comparison_type: str = Form("basic"),
    user_id: str = Depends(get_current_user_id),
):
    """Compare two Word documents"""

    # Validate file types
    for file in [file1, file2]:
        if not file.filename.lower().endswith((".docx", ".doc")):
            raise HTTPException(
                status_code=400, detail="Only .docx and .doc files are supported"
            )

    try:
        # Read file contents
        file1_content = await file1.read()
        file2_content = await file2.read()

        # Compare documents
        result = word_service.compare_word_documents(
            file1_content, file2_content, comparison_type
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        result.update(
            {
                "file1_name": file1.filename,
                "file2_name": file2.filename,
                "comparison_type": comparison_type,
            }
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.get("/metadata")
async def extract_word_metadata(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Extract metadata from Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Load document and extract metadata
        processor = word_service.docx_processor
        document = processor.load_document_from_bytes(file_content)
        metadata = processor.extract_document_metadata(document)

        return {"success": True, "filename": file.filename, "metadata": metadata}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Metadata extraction failed: {str(e)}"
        )


@router.get("/styles")
async def extract_word_styles(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Extract style definitions from Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Load document and extract styles
        processor = word_service.docx_processor
        document = processor.load_document_from_bytes(file_content)
        styles = processor.extract_styles(document)

        return {
            "success": True,
            "filename": file.filename,
            "styles": styles,
            "style_count": len(styles),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Style extraction failed: {str(e)}"
        )


@router.get("/structure")
async def analyze_word_structure(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Analyze Word document structure"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Process document to get structure analysis
        result = await word_service.process_word_document(
            file_content, file.filename, user_id, {"analyze_structure": True}
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "success": True,
            "filename": file.filename,
            "structure": result["structure"],
            "analysis": result["analysis"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Structure analysis failed: {str(e)}"
        )


@router.get("/supported-formats")
async def get_supported_formats(user_id: str = Depends(get_current_user_id)):
    """Get supported file formats and conversion options"""

    formats = word_service.get_supported_formats()

    return {"success": True, "formats": formats}


@router.post("/batch-process")
async def batch_process_word_documents(
    files: list[UploadFile] = File(...),
    processing_options: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id),
):
    """Batch process multiple Word documents"""

    # Validate file count
    if len(files) > 10:
        raise HTTPException(
            status_code=400, detail="Maximum 10 files allowed per batch"
        )

    # Parse processing options
    options = {}
    if processing_options:
        try:
            options = json.loads(processing_options)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, detail="Invalid processing options JSON"
            )

    results = []

    for file in files:
        # Validate file type
        if not file.filename.lower().endswith((".docx", ".doc")):
            results.append(
                {
                    "filename": file.filename,
                    "success": False,
                    "error": "Unsupported file type",
                }
            )
            continue

        try:
            # Read file content
            file_content = await file.read()

            # Process document
            result = await word_service.process_word_document(
                file_content, file.filename, user_id, options
            )

            results.append(
                {
                    "filename": file.filename,
                    "success": result["success"],
                    "document_id": result.get("document_id"),
                    "metadata": result.get("metadata"),
                    "analysis": result.get("analysis"),
                    "error": result.get("error"),
                }
            )

        except Exception as e:
            results.append(
                {"filename": file.filename, "success": False, "error": str(e)}
            )

    # Calculate batch statistics
    successful_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - successful_count

    return {
        "success": True,
        "batch_results": results,
        "statistics": {
            "total_files": len(files),
            "successful": successful_count,
            "failed": failed_count,
            "success_rate": (successful_count / len(files)) * 100 if files else 0,
        },
    }


@router.post("/xml/structure")
async def analyze_xml_structure(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Analyze XML structure of Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Analyze XML structure
        result = xml_service.extract_xml_structure(file_content)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return {"success": True, "filename": file.filename, "xml_structure": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"XML analysis failed: {str(e)}")


@router.post("/xml/custom-parts")
async def extract_custom_xml_parts(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Extract custom XML parts from Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Extract custom XML parts
        result = xml_service.extract_custom_xml_parts(file_content)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return {"success": True, "filename": file.filename, "custom_xml": result}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Custom XML extraction failed: {str(e)}"
        )


@router.post("/xml/variables")
async def extract_document_variables(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Extract document variables from Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Extract document variables
        result = xml_service.extract_document_variables(file_content)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return {"success": True, "filename": file.filename, "variables": result}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Variable extraction failed: {str(e)}"
        )


@router.post("/xml/form-fields")
async def extract_form_fields(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Extract form fields from Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Extract form fields
        result = xml_service.extract_form_fields(file_content)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return {"success": True, "filename": file.filename, "form_fields": result}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Form field extraction failed: {str(e)}"
        )


@router.post("/xml/hyperlinks")
async def extract_hyperlinks(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Extract hyperlinks from Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Extract hyperlinks
        result = xml_service.extract_hyperlinks(file_content)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return {"success": True, "filename": file.filename, "hyperlinks": result}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Hyperlink extraction failed: {str(e)}"
        )


@router.post("/xml/complexity")
async def analyze_xml_complexity(
    file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)
):
    """Analyze XML complexity of Word document"""

    # Validate file type
    if not file.filename.lower().endswith((".docx", ".doc")):
        raise HTTPException(
            status_code=400, detail="Only .docx and .doc files are supported"
        )

    try:
        # Read file content
        file_content = await file.read()

        # Analyze complexity
        result = xml_service.analyze_xml_complexity(file_content)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "success": True,
            "filename": file.filename,
            "complexity_analysis": result,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Complexity analysis failed: {str(e)}"
        )
