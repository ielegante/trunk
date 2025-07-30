"""Simple single-process server for Trunk document processing.

This server is designed for small law firms (1-50 lawyers) and requires
minimal configuration. It uses SQLite for storage and runs as a single process.
"""

import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Simple logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import our document processing components
from .converters import BaseConverter, GoogleDocsConverter, PDFConverter, WordConverter
from .permissions import PermissionSyncManager
from .references import CrossDocumentReferenceManager
from .templates import TemplateManager


# Simple configuration from environment
class SimpleConfig:
    """Simple configuration for small law firm deployment."""

    def __init__(self):
        self.port = int(os.getenv("TRUNK_PORT", "8080"))
        self.data_dir = Path(os.getenv("TRUNK_DATA_DIR", "/app/data"))
        self.log_dir = Path(os.getenv("TRUNK_LOG_DIR", "/app/logs"))
        self.cache_dir = Path(os.getenv("TRUNK_CACHE_DIR", "/app/cache"))
        self.db_path = Path(os.getenv("TRUNK_DB_PATH", self.data_dir / "trunk.db"))

        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with simple schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Simple document tracking table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_id TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                content_hash TEXT,
                last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """
        )

        # Simple template table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                variables TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Simple reference tracking
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS document_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_doc_id INTEGER,
                target_doc_id INTEGER,
                reference_type TEXT,
                reference_text TEXT,
                FOREIGN KEY (source_doc_id) REFERENCES documents(id),
                FOREIGN KEY (target_doc_id) REFERENCES documents(id)
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")


# Create FastAPI app
app = FastAPI(
    title="Trunk Document Processing",
    description="Simple document version control for law firms",
    version="1.0.0",
)

# Add CORS for Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize configuration
config = SimpleConfig()

# Initialize simple in-memory caches
document_cache = {}
template_cache = {}

# Initialize managers with simple configuration
template_manager = TemplateManager(config.data_dir / "templates")
reference_manager = CrossDocumentReferenceManager()


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    try:
        # Check database connection
        conn = sqlite3.connect(str(config.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()

        return {
            "status": "healthy",
            "service": "trunk-document-processing",
            "database": "connected",
            "cache_dir": str(config.cache_dir),
            "data_dir": str(config.data_dir),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.post("/api/v1/convert/google-docs")
async def convert_google_docs(drive_id: str, content: str):
    """Convert Google Docs content to Markdown."""
    try:
        converter = GoogleDocsConverter()
        markdown = converter.to_markdown(content)

        # Store in simple cache
        document_cache[drive_id] = {"content": markdown, "type": "google-docs"}

        # Update database
        conn = sqlite3.connect(str(config.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO documents (drive_id, file_name, file_type, content_hash)
            VALUES (?, ?, ?, ?)
        """,
            (drive_id, f"doc_{drive_id}", "google-docs", hash(markdown)),
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "drive_id": drive_id,
            "markdown": markdown,
            "cached": True,
        }
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/convert/word")
async def convert_word(drive_id: str, file_content: bytes):
    """Convert Word document to Markdown."""
    try:
        converter = WordConverter()
        # Save temporarily
        temp_path = config.cache_dir / f"temp_{drive_id}.docx"
        with open(temp_path, "wb") as f:
            f.write(file_content)

        markdown = converter.to_markdown(str(temp_path))

        # Cleanup
        temp_path.unlink()

        # Store in cache
        document_cache[drive_id] = {"content": markdown, "type": "word"}

        return {"success": True, "drive_id": drive_id, "markdown": markdown}
    except Exception as e:
        logger.error(f"Word conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/templates")
async def list_templates():
    """List available templates."""
    try:
        conn = sqlite3.connect(str(config.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name, variables, created_at FROM templates")
        templates = cursor.fetchall()
        conn.close()

        return {
            "templates": [
                {
                    "name": t[0],
                    "variables": t[1].split(",") if t[1] else [],
                    "created_at": t[2],
                }
                for t in templates
            ]
        }
    except Exception as e:
        logger.error(f"Template listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/templates/create")
async def create_template(name: str, content: str, variables: list = None):
    """Create a new template."""
    try:
        conn = sqlite3.connect(str(config.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO templates (name, content, variables)
            VALUES (?, ?, ?)
        """,
            (name, content, ",".join(variables) if variables else ""),
        )
        conn.commit()
        conn.close()

        return {"success": True, "template_name": name, "variables": variables or []}
    except Exception as e:
        logger.error(f"Template creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/references/{drive_id}")
async def get_document_references(drive_id: str):
    """Get references for a document."""
    try:
        conn = sqlite3.connect(str(config.db_path))
        cursor = conn.cursor()

        # Get document ID
        cursor.execute("SELECT id FROM documents WHERE drive_id = ?", (drive_id,))
        doc_result = cursor.fetchone()

        if not doc_result:
            conn.close()
            return {"references": [], "referenced_by": []}

        doc_id = doc_result[0]

        # Get outgoing references
        cursor.execute(
            """
            SELECT d.drive_id, d.file_name, r.reference_text
            FROM document_references r
            JOIN documents d ON r.target_doc_id = d.id
            WHERE r.source_doc_id = ?
        """,
            (doc_id,),
        )
        references = cursor.fetchall()

        # Get incoming references
        cursor.execute(
            """
            SELECT d.drive_id, d.file_name, r.reference_text
            FROM document_references r
            JOIN documents d ON r.source_doc_id = d.id
            WHERE r.target_doc_id = ?
        """,
            (doc_id,),
        )
        referenced_by = cursor.fetchall()

        conn.close()

        return {
            "references": [
                {"drive_id": r[0], "name": r[1], "text": r[2]} for r in references
            ],
            "referenced_by": [
                {"drive_id": r[0], "name": r[1], "text": r[2]} for r in referenced_by
            ],
        }
    except Exception as e:
        logger.error(f"Reference lookup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Simple status page."""
    return {
        "service": "Trunk Document Processing",
        "status": "running",
        "description": "Simple document version control for law firms",
        "endpoints": {
            "health": "/health",
            "convert_google_docs": "/api/v1/convert/google-docs",
            "convert_word": "/api/v1/convert/word",
            "templates": "/api/v1/templates",
            "references": "/api/v1/references/{drive_id}",
        },
    }


def main():
    """Run the simple server."""
    logger.info(f"Starting Trunk Document Processing on port {config.port}")
    logger.info(f"Data directory: {config.data_dir}")
    logger.info(f"Database: {config.db_path}")

    uvicorn.run(
        app, host="0.0.0.0", port=config.port, log_level="info", access_log=True
    )


if __name__ == "__main__":
    main()
