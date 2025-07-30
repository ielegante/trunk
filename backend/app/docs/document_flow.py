import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.docs.gdocs_api import DocumentConverter, GoogleDocsAPI
from app.git_ops.repository import GitOperations
from google.oauth2.credentials import Credentials


class DocumentFlowManager:
    """Manages the flow of documents between Google Docs and Git repositories"""

    def __init__(self, base_path: str = "./document_sync"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self.git_ops = GitOperations()

    def sync_document_to_git(
        self,
        credentials: Credentials,
        document_id: str,
        repo_name: str,
        user_id: str,
        file_path: str,
        format_type: str = "markdown",
    ) -> Dict:
        """Sync a Google Doc to a git repository"""
        try:
            # Initialize Google Docs API
            gdocs_api = GoogleDocsAPI(credentials)

            # Get document from Google Docs
            doc_result = gdocs_api.get_document(document_id)
            if not doc_result["success"]:
                return doc_result

            document = doc_result["document"]

            # Convert document to desired format
            if format_type == "markdown":
                content = DocumentConverter.convert_to_markdown(document)
                file_extension = ".md"
            else:
                content = DocumentConverter.extract_text_from_document(document)
                file_extension = ".txt"

            # Ensure file path has correct extension
            if not file_path.endswith(file_extension):
                file_path = f"{file_path}{file_extension}"

            # Get repository path
            repo_path = self.git_ops.base_path / user_id / repo_name
            if not repo_path.exists():
                return {
                    "success": False,
                    "error": f"Repository {repo_name} not found for user {user_id}",
                }

            # Write content to file
            full_file_path = repo_path / file_path
            full_file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Create metadata file
            metadata = {
                "document_id": document_id,
                "title": document.get("title", ""),
                "sync_time": datetime.utcnow().isoformat(),
                "format": format_type,
                "file_path": file_path,
            }

            metadata_path = repo_path / ".trunk" / "documents" / f"{document_id}.json"
            metadata_path.parent.mkdir(parents=True, exist_ok=True)

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            return {
                "success": True,
                "message": f"Document synced to {file_path}",
                "document_title": document.get("title", ""),
                "file_path": file_path,
                "content_length": len(content),
                "format": format_type,
            }

        except Exception as e:
            return {"success": False, "error": f"Document sync failed: {str(e)}"}

    def commit_document_changes(
        self,
        repo_name: str,
        user_id: str,
        document_id: str,
        commit_message: Optional[str] = None,
    ) -> Dict:
        """Commit document changes to git repository"""
        try:
            # Get document metadata
            repo_path = self.git_ops.base_path / user_id / repo_name
            metadata_path = repo_path / ".trunk" / "documents" / f"{document_id}.json"

            if not metadata_path.exists():
                return {
                    "success": False,
                    "error": f"Document metadata not found for {document_id}",
                }

            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            file_path = metadata.get("file_path")
            document_title = metadata.get("title", "Unknown Document")

            if not commit_message:
                commit_message = f"docs: sync '{document_title}' from Google Docs\n\nDocument ID: {document_id}\nSync time: {datetime.utcnow().isoformat()}"

            # Commit changes including metadata
            files_to_commit = [file_path, str(metadata_path.relative_to(repo_path))]
            result = self.git_ops.commit_changes(
                repo_name, user_id, commit_message, files_to_commit
            )

            return result

        except Exception as e:
            return {"success": False, "error": f"Commit failed: {str(e)}"}

    def get_document_sync_status(self, repo_name: str, user_id: str) -> Dict:
        """Get status of all synced documents in repository"""
        try:
            repo_path = self.git_ops.base_path / user_id / repo_name
            documents_path = repo_path / ".trunk" / "documents"

            if not documents_path.exists():
                return {"success": True, "synced_documents": [], "count": 0}

            synced_docs = []
            for metadata_file in documents_path.glob("*.json"):
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                file_path = repo_path / metadata.get("file_path", "")
                metadata["file_exists"] = file_path.exists()
                metadata["last_modified"] = (
                    file_path.stat().st_mtime if file_path.exists() else None
                )

                synced_docs.append(metadata)

            return {
                "success": True,
                "synced_documents": synced_docs,
                "count": len(synced_docs),
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get sync status: {str(e)}"}

    def setup_document_watch(
        self, credentials: Credentials, document_id: str, webhook_url: str
    ) -> Dict:
        """Set up real-time watching for document changes"""
        try:
            gdocs_api = GoogleDocsAPI(credentials)
            return gdocs_api.watch_document(document_id, webhook_url)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to setup document watch: {str(e)}",
            }

    def handle_document_change_webhook(
        self, credentials: Credentials, document_id: str, repo_name: str, user_id: str
    ) -> Dict:
        """Handle webhook notification for document changes"""
        try:
            # Get document metadata to find file path
            repo_path = self.git_ops.base_path / user_id / repo_name
            metadata_path = repo_path / ".trunk" / "documents" / f"{document_id}.json"

            if not metadata_path.exists():
                return {
                    "success": False,
                    "error": f"Document not tracked in repository: {document_id}",
                }

            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            file_path = metadata.get("file_path")
            format_type = metadata.get("format", "markdown")

            # Re-sync the document
            sync_result = self.sync_document_to_git(
                credentials, document_id, repo_name, user_id, file_path, format_type
            )

            if not sync_result["success"]:
                return sync_result

            # Auto-commit the changes
            commit_result = self.commit_document_changes(
                repo_name,
                user_id,
                document_id,
                f"docs: auto-sync '{metadata.get('title', 'Unknown')}' from webhook\n\nTriggered by Google Docs change notification",
            )

            return {
                "success": True,
                "message": "Document change processed successfully",
                "sync_result": sync_result,
                "commit_result": commit_result,
            }

        except Exception as e:
            return {"success": False, "error": f"Webhook processing failed: {str(e)}"}
