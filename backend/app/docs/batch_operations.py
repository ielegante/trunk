import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from app.docs.document_flow import DocumentFlowManager
from app.docs.enhanced_converter import EnhancedDocumentConverter
from app.docs.gdocs_api import GoogleDocsAPI
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class BatchDocumentProcessor:
    """Handle batch operations for multiple documents"""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.doc_flow = DocumentFlowManager()

    def batch_sync_documents(
        self, credentials: Credentials, sync_requests: List[Dict], user_id: str
    ) -> Dict:
        """Sync multiple documents in batch"""
        results = []
        failed_syncs = []

        def sync_single_document(request):
            try:
                return self.doc_flow.sync_document_to_git(
                    credentials,
                    request["document_id"],
                    request["repo_name"],
                    user_id,
                    request["file_path"],
                    request.get("format_type", "markdown"),
                )
            except Exception as e:
                logger.error(
                    f"Failed to sync document {request['document_id']}: {str(e)}"
                )
                return {
                    "success": False,
                    "document_id": request["document_id"],
                    "error": str(e),
                }

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_request = {
                executor.submit(sync_single_document, request): request
                for request in sync_requests
            }

            for future in as_completed(future_to_request):
                request = future_to_request[future]
                try:
                    result = future.result()
                    if result["success"]:
                        results.append(result)
                    else:
                        failed_syncs.append(
                            {
                                "document_id": request["document_id"],
                                "error": result.get("error", "Unknown error"),
                            }
                        )
                except Exception as e:
                    failed_syncs.append(
                        {"document_id": request["document_id"], "error": str(e)}
                    )

        return {
            "success": True,
            "successful_syncs": len(results),
            "failed_syncs": len(failed_syncs),
            "results": results,
            "failures": failed_syncs,
        }

    def batch_export_documents(
        self,
        credentials: Credentials,
        document_ids: List[str],
        format_type: str = "text/plain",
    ) -> Dict:
        """Export multiple documents in batch"""
        gdocs_api = GoogleDocsAPI(credentials)
        results = []
        failed_exports = []

        def export_single_document(doc_id):
            try:
                return gdocs_api.export_document(doc_id, format_type)
            except Exception as e:
                logger.error(f"Failed to export document {doc_id}: {str(e)}")
                return {"success": False, "document_id": doc_id, "error": str(e)}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_doc_id = {
                executor.submit(export_single_document, doc_id): doc_id
                for doc_id in document_ids
            }

            for future in as_completed(future_to_doc_id):
                doc_id = future_to_doc_id[future]
                try:
                    result = future.result()
                    if result["success"]:
                        result["document_id"] = doc_id
                        results.append(result)
                    else:
                        failed_exports.append(
                            {
                                "document_id": doc_id,
                                "error": result.get("error", "Unknown error"),
                            }
                        )
                except Exception as e:
                    failed_exports.append({"document_id": doc_id, "error": str(e)})

        return {
            "success": True,
            "successful_exports": len(results),
            "failed_exports": len(failed_exports),
            "results": results,
            "failures": failed_exports,
        }

    def batch_convert_documents(
        self,
        credentials: Credentials,
        document_ids: List[str],
        output_format: str = "markdown",
    ) -> Dict:
        """Convert multiple documents to specified format"""
        gdocs_api = GoogleDocsAPI(credentials)
        results = []
        failed_conversions = []

        def convert_single_document(doc_id):
            try:
                # Get document
                doc_result = gdocs_api.get_document(doc_id)
                if not doc_result["success"]:
                    return doc_result

                document = doc_result["document"]

                # Convert based on format
                if output_format == "markdown":
                    converted_content = EnhancedDocumentConverter.convert_to_markdown(
                        document
                    )
                elif output_format == "summary":
                    converted_content = (
                        EnhancedDocumentConverter.generate_document_summary(document)
                    )
                else:
                    converted_content = (
                        EnhancedDocumentConverter.extract_text_from_document(document)
                    )

                metadata = EnhancedDocumentConverter.extract_document_metadata(document)

                return {
                    "success": True,
                    "document_id": doc_id,
                    "title": document.get("title", ""),
                    "content": converted_content,
                    "metadata": metadata,
                    "format": output_format,
                }

            except Exception as e:
                logger.error(f"Failed to convert document {doc_id}: {str(e)}")
                return {"success": False, "document_id": doc_id, "error": str(e)}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_doc_id = {
                executor.submit(convert_single_document, doc_id): doc_id
                for doc_id in document_ids
            }

            for future in as_completed(future_to_doc_id):
                doc_id = future_to_doc_id[future]
                try:
                    result = future.result()
                    if result["success"]:
                        results.append(result)
                    else:
                        failed_conversions.append(
                            {
                                "document_id": doc_id,
                                "error": result.get("error", "Unknown error"),
                            }
                        )
                except Exception as e:
                    failed_conversions.append({"document_id": doc_id, "error": str(e)})

        return {
            "success": True,
            "successful_conversions": len(results),
            "failed_conversions": len(failed_conversions),
            "results": results,
            "failures": failed_conversions,
        }

    def batch_analyze_documents(
        self, credentials: Credentials, document_ids: List[str]
    ) -> Dict:
        """Analyze multiple documents for metadata and statistics"""
        gdocs_api = GoogleDocsAPI(credentials)
        results = []
        failed_analyses = []

        def analyze_single_document(doc_id):
            try:
                doc_result = gdocs_api.get_document(doc_id)
                if not doc_result["success"]:
                    return doc_result

                document = doc_result["document"]
                metadata = EnhancedDocumentConverter.extract_document_metadata(document)

                # Add additional analysis
                content = document.get("body", {}).get("content", [])
                analysis = {
                    "has_tables": any("table" in elem for elem in content),
                    "has_images": any(
                        "inlineObjectElement" in elem for elem in content
                    ),
                    "has_lists": any(
                        "paragraph" in elem
                        and elem["paragraph"].get("paragraphStyle", {}).get("bullet")
                        for elem in content
                    ),
                    "structure_complexity": len(metadata["headings"]),
                    "estimated_read_time": max(
                        1, metadata["word_count"] // 200
                    ),  # ~200 words per minute
                }

                return {
                    "success": True,
                    "document_id": doc_id,
                    "metadata": metadata,
                    "analysis": analysis,
                }

            except Exception as e:
                logger.error(f"Failed to analyze document {doc_id}: {str(e)}")
                return {"success": False, "document_id": doc_id, "error": str(e)}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_doc_id = {
                executor.submit(analyze_single_document, doc_id): doc_id
                for doc_id in document_ids
            }

            for future in as_completed(future_to_doc_id):
                doc_id = future_to_doc_id[future]
                try:
                    result = future.result()
                    if result["success"]:
                        results.append(result)
                    else:
                        failed_analyses.append(
                            {
                                "document_id": doc_id,
                                "error": result.get("error", "Unknown error"),
                            }
                        )
                except Exception as e:
                    failed_analyses.append({"document_id": doc_id, "error": str(e)})

        return {
            "success": True,
            "successful_analyses": len(results),
            "failed_analyses": len(failed_analyses),
            "results": results,
            "failures": failed_analyses,
            "summary": {
                "total_documents": len(document_ids),
                "avg_word_count": (
                    sum(r["metadata"]["word_count"] for r in results) / len(results)
                    if results
                    else 0
                ),
                "total_headings": sum(len(r["metadata"]["headings"]) for r in results),
                "total_tables": sum(r["metadata"]["tables_count"] for r in results),
                "total_images": sum(r["metadata"]["images_count"] for r in results),
            },
        }
