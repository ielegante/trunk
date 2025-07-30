import re
from typing import Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleDocsAPI:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.docs_service = build("docs", "v1", credentials=credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)

    def get_document(self, document_id: str) -> Dict:
        """Get Google Docs document content"""
        try:
            document = (
                self.docs_service.documents().get(documentId=document_id).execute()
            )
            return {
                "success": True,
                "document": document,
                "title": document.get("title", ""),
                "document_id": document_id,
            }
        except HttpError as e:
            return {"success": False, "error": f"Failed to fetch document: {str(e)}"}

    def list_documents(self, folder_id: Optional[str] = None) -> Dict:
        """List Google Docs documents accessible to user"""
        try:
            query = "mimeType='application/vnd.google-apps.document'"
            if folder_id:
                query += f" and '{folder_id}' in parents"

            results = (
                self.drive_service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, modifiedTime, owners, webViewLink)",
                )
                .execute()
            )

            documents = results.get("files", [])

            return {"success": True, "documents": documents, "count": len(documents)}
        except HttpError as e:
            return {"success": False, "error": f"Failed to list documents: {str(e)}"}

    def get_document_revisions(self, document_id: str) -> Dict:
        """Get revision history for a document"""
        try:
            revisions = (
                self.drive_service.revisions()
                .list(
                    fileId=document_id,
                    fields="revisions(id, modifiedTime, lastModifyingUser)",
                )
                .execute()
            )

            return {"success": True, "revisions": revisions.get("revisions", [])}
        except HttpError as e:
            return {"success": False, "error": f"Failed to get revisions: {str(e)}"}

    def export_document(self, document_id: str, mime_type: str = "text/plain") -> Dict:
        """Export document in specified format"""
        try:
            # Available formats: text/plain, text/html, application/pdf
            content = (
                self.drive_service.files()
                .export(fileId=document_id, mimeType=mime_type)
                .execute()
            )

            return {
                "success": True,
                "content": (
                    content.decode("utf-8") if isinstance(content, bytes) else content
                ),
                "mime_type": mime_type,
            }
        except HttpError as e:
            return {"success": False, "error": f"Failed to export document: {str(e)}"}

    def watch_document(self, document_id: str, webhook_url: str) -> Dict:
        """Set up webhook for document changes"""
        try:
            # Create a watch request for the document
            body = {
                "id": f"trunk-watch-{document_id}",
                "type": "web_hook",
                "address": webhook_url,
                "token": f"doc-{document_id}",
            }

            watch_response = (
                self.drive_service.files()
                .watch(fileId=document_id, body=body)
                .execute()
            )

            return {
                "success": True,
                "watch_id": watch_response.get("id"),
                "resource_id": watch_response.get("resourceId"),
                "expiration": watch_response.get("expiration"),
            }
        except HttpError as e:
            return {
                "success": False,
                "error": f"Failed to set up document watch: {str(e)}",
            }

    def stop_watching(self, channel_id: str, resource_id: str) -> Dict:
        """Stop watching a document"""
        try:
            body = {"id": channel_id, "resourceId": resource_id}

            self.drive_service.channels().stop(body=body).execute()

            return {"success": True, "message": "Document watch stopped successfully"}
        except HttpError as e:
            return {
                "success": False,
                "error": f"Failed to stop watching document: {str(e)}",
            }


class DocumentConverter:
    """Convert Google Docs content to various formats"""

    @staticmethod
    def extract_text_from_document(document: Dict) -> str:
        """Extract plain text from Google Docs document structure"""
        content = document.get("body", {}).get("content", [])
        text_parts = []

        for element in content:
            if "paragraph" in element:
                paragraph_text = DocumentConverter._extract_paragraph_text(
                    element["paragraph"]
                )
                if paragraph_text.strip():
                    text_parts.append(paragraph_text)
            elif "table" in element:
                table_text = DocumentConverter._extract_table_text(element["table"])
                if table_text.strip():
                    text_parts.append(table_text)

        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_paragraph_text(paragraph: Dict) -> str:
        """Extract text from a paragraph element"""
        elements = paragraph.get("elements", [])
        text_parts = []

        for element in elements:
            if "textRun" in element:
                text_content = element["textRun"].get("content", "")
                text_parts.append(text_content)

        return "".join(text_parts)

    @staticmethod
    def _extract_table_text(table: Dict) -> str:
        """Extract text from a table element"""
        rows = table.get("tableRows", [])
        table_text = []

        for row in rows:
            row_text = []
            cells = row.get("tableCells", [])

            for cell in cells:
                cell_content = cell.get("content", [])
                cell_text = []

                for element in cell_content:
                    if "paragraph" in element:
                        paragraph_text = DocumentConverter._extract_paragraph_text(
                            element["paragraph"]
                        )
                        cell_text.append(paragraph_text.strip())

                row_text.append(" ".join(cell_text))

            table_text.append(" | ".join(row_text))

        return "\n".join(table_text)

    @staticmethod
    def convert_to_markdown(document: Dict) -> str:
        """Convert Google Docs document to Markdown format"""
        content = document.get("body", {}).get("content", [])
        markdown_parts = []

        for element in content:
            if "paragraph" in element:
                markdown_text = DocumentConverter._convert_paragraph_to_markdown(
                    element["paragraph"]
                )
                if markdown_text.strip():
                    markdown_parts.append(markdown_text)
            elif "table" in element:
                table_markdown = DocumentConverter._convert_table_to_markdown(
                    element["table"]
                )
                if table_markdown.strip():
                    markdown_parts.append(table_markdown)

        return "\n\n".join(markdown_parts)

    @staticmethod
    def _convert_paragraph_to_markdown(paragraph: Dict) -> str:
        """Convert paragraph to Markdown with formatting"""
        elements = paragraph.get("elements", [])
        text_parts = []

        for element in elements:
            if "textRun" in element:
                text_run = element["textRun"]
                content = text_run.get("content", "")
                text_style = text_run.get("textStyle", {})

                # Apply formatting
                if text_style.get("bold"):
                    content = f"**{content}**"
                if text_style.get("italic"):
                    content = f"*{content}*"

                text_parts.append(content)

        paragraph_text = "".join(text_parts)

        # Check paragraph style for headers
        paragraph_style = paragraph.get("paragraphStyle", {})
        named_style = paragraph_style.get("namedStyleType", "")

        if "HEADING_1" in named_style:
            return f"# {paragraph_text.strip()}"
        elif "HEADING_2" in named_style:
            return f"## {paragraph_text.strip()}"
        elif "HEADING_3" in named_style:
            return f"### {paragraph_text.strip()}"

        return paragraph_text

    @staticmethod
    def _convert_table_to_markdown(table: Dict) -> str:
        """Convert table to Markdown format"""
        rows = table.get("tableRows", [])
        markdown_rows = []

        for i, row in enumerate(rows):
            cells = row.get("tableCells", [])
            cell_contents = []

            for cell in cells:
                cell_content = cell.get("content", [])
                cell_text_parts = []

                for element in cell_content:
                    if "paragraph" in element:
                        paragraph_text = DocumentConverter._extract_paragraph_text(
                            element["paragraph"]
                        )
                        cell_text_parts.append(paragraph_text.strip())

                cell_contents.append(" ".join(cell_text_parts))

            markdown_rows.append(f"| {' | '.join(cell_contents)} |")

            # Add header separator after first row
            if i == 0:
                separator = f"| {' | '.join(['---'] * len(cell_contents))} |"
                markdown_rows.append(separator)

        return "\n".join(markdown_rows)
