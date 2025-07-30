from typing import Dict, List, Optional

from app.api.auth_routes import get_current_user_id
from app.auth.oauth import JWTHandler
from app.docs.batch_operations import BatchDocumentProcessor
from app.docs.document_flow import DocumentFlowManager
from app.docs.enhanced_converter import EnhancedDocumentConverter
from app.docs.gdocs_api import GoogleDocsAPI
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from google.oauth2.credentials import Credentials
from pydantic import BaseModel

router = APIRouter(prefix="/docs", tags=["documents"])
jwt_handler = JWTHandler()
doc_flow = DocumentFlowManager()
batch_processor = BatchDocumentProcessor()


class SyncDocumentRequest(BaseModel):
    document_id: str
    repo_name: str
    file_path: str
    format_type: str = "markdown"


class WatchDocumentRequest(BaseModel):
    document_id: str
    webhook_url: str


class BatchSyncRequest(BaseModel):
    sync_requests: List[Dict]


class BatchProcessRequest(BaseModel):
    document_ids: List[str]
    format_type: str = "markdown"


def get_user_credentials(user_id: str = Depends(get_current_user_id)) -> Credentials:
    """Get Google credentials for the current user"""
    from app.auth.token_store import token_store

    credentials = token_store.get_credentials(user_id)
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="User credentials not found. Please re-authenticate.",
        )

    # Check if credentials are expired and refresh if possible
    if credentials.expired and credentials.refresh_token:
        refreshed_credentials = token_store.refresh_credentials(user_id)
        if refreshed_credentials:
            credentials = refreshed_credentials
        else:
            raise HTTPException(
                status_code=401,
                detail="Credentials expired and refresh failed. Please re-authenticate.",
            )

    return credentials


@router.get("/list")
async def list_documents(
    folder_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """List Google Docs documents accessible to user"""
    gdocs_api = GoogleDocsAPI(credentials)
    result = gdocs_api.list_documents(folder_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/document/{document_id}")
async def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Get specific Google Docs document"""
    gdocs_api = GoogleDocsAPI(credentials)
    result = gdocs_api.get_document(document_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/sync")
async def sync_document_to_git(
    request: SyncDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Sync Google Docs document to git repository"""
    result = doc_flow.sync_document_to_git(
        credentials,
        request.document_id,
        request.repo_name,
        user_id,
        request.file_path,
        request.format_type,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/commit/{document_id}")
async def commit_document_changes(
    document_id: str,
    repo_name: str,
    commit_message: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
):
    """Commit document changes to git repository"""
    result = doc_flow.commit_document_changes(
        repo_name, user_id, document_id, commit_message
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/sync-status/{repo_name}")
async def get_sync_status(repo_name: str, user_id: str = Depends(get_current_user_id)):
    """Get document sync status for repository"""
    result = doc_flow.get_document_sync_status(repo_name, user_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/watch")
async def setup_document_watch(
    request: WatchDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Set up real-time watching for document changes"""
    result = doc_flow.setup_document_watch(
        credentials, request.document_id, request.webhook_url
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/webhook/document-change")
async def handle_document_change_webhook(
    request: Request,
    x_goog_channel_id: Optional[str] = Header(None),
    x_goog_resource_id: Optional[str] = Header(None),
):
    """Handle Google Drive webhook notifications for document changes"""
    try:
        # Extract document ID from channel ID (format: trunk-watch-{document_id})
        if not x_goog_channel_id or not x_goog_channel_id.startswith("trunk-watch-"):
            raise HTTPException(status_code=400, detail="Invalid webhook channel")

        document_id = x_goog_channel_id.replace("trunk-watch-", "")

        # TODO: Get user credentials and repository info from stored webhook metadata
        # For now, return acknowledgment
        return {
            "success": True,
            "message": "Webhook received",
            "document_id": document_id,
            "channel_id": x_goog_channel_id,
            "resource_id": x_goog_resource_id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Webhook processing failed: {str(e)}"
        )


@router.get("/export/{document_id}")
async def export_document(
    document_id: str,
    format_type: str = "text/plain",
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Export Google Docs document in specified format"""
    gdocs_api = GoogleDocsAPI(credentials)
    result = gdocs_api.export_document(document_id, format_type)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/convert/{document_id}")
async def convert_document(
    document_id: str,
    format_type: str = "markdown",
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Convert Google Docs document to specified format with enhanced formatting"""
    gdocs_api = GoogleDocsAPI(credentials)
    doc_result = gdocs_api.get_document(document_id)

    if not doc_result["success"]:
        raise HTTPException(status_code=404, detail=doc_result["error"])

    document = doc_result["document"]

    try:
        if format_type == "markdown":
            converted_content = EnhancedDocumentConverter.convert_to_markdown(document)
        elif format_type == "summary":
            converted_content = EnhancedDocumentConverter.generate_document_summary(
                document
            )
        else:
            converted_content = EnhancedDocumentConverter.extract_text_from_document(
                document
            )

        metadata = EnhancedDocumentConverter.extract_document_metadata(document)

        return {
            "success": True,
            "document_id": document_id,
            "title": document.get("title", ""),
            "content": converted_content,
            "metadata": metadata,
            "format": format_type,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.post("/batch/sync")
async def batch_sync_documents(
    request: BatchSyncRequest,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Sync multiple documents in batch"""
    result = batch_processor.batch_sync_documents(
        credentials, request.sync_requests, user_id
    )

    return result


@router.post("/batch/convert")
async def batch_convert_documents(
    request: BatchProcessRequest,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Convert multiple documents in batch"""
    result = batch_processor.batch_convert_documents(
        credentials, request.document_ids, request.format_type
    )

    return result


@router.post("/batch/analyze")
async def batch_analyze_documents(
    request: BatchProcessRequest,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Analyze multiple documents for metadata and statistics"""
    result = batch_processor.batch_analyze_documents(credentials, request.document_ids)

    return result


@router.get("/metadata/{document_id}")
async def get_document_metadata(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    credentials: Credentials = Depends(get_user_credentials),
):
    """Get comprehensive metadata for a document"""
    gdocs_api = GoogleDocsAPI(credentials)
    doc_result = gdocs_api.get_document(document_id)

    if not doc_result["success"]:
        raise HTTPException(status_code=404, detail=doc_result["error"])

    document = doc_result["document"]
    metadata = EnhancedDocumentConverter.extract_document_metadata(document)

    return {"success": True, "document_id": document_id, "metadata": metadata}
