"""Neo4j database configuration and connection management."""

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Optional

from app.config import settings
from neo4j import GraphDatabase, Session, Transaction
from neo4j.exceptions import AuthError, ServiceUnavailable

logger = logging.getLogger(__name__)


class Neo4jConfig:
    """Neo4j database configuration."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.max_connection_lifetime = 3600
        self.max_connection_pool_size = 50
        self.connection_acquisition_timeout = 60
        self.encrypted = os.getenv("NEO4J_ENCRYPTED", "false").lower() == "true"


class Neo4jConnection:
    """Manages Neo4j database connections."""

    def __init__(self, config: Neo4jConfig):
        self.config = config
        self._driver = None
        self._connect()

    def _connect(self):
        """Establish connection to Neo4j database."""
        try:
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.username, self.config.password),
                max_connection_lifetime=self.config.max_connection_lifetime,
                max_connection_pool_size=self.config.max_connection_pool_size,
                connection_acquisition_timeout=self.config.connection_acquisition_timeout,
                encrypted=self.config.encrypted,
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j at {self.config.uri}")
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {str(e)}")
            raise
        except AuthError as e:
            logger.error(f"Neo4j authentication failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise

    @contextmanager
    def session(self, database: Optional[str] = None):
        """Create a session context manager."""
        if not self._driver:
            self._connect()

        session = self._driver.session(database=database or self.config.database)
        try:
            yield session
        finally:
            session.close()

    def close(self):
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> list:
        """Execute a query and return results."""
        with self.session(database) as session:
            result = session.run(query, parameters or {})
            return list(result)

    def execute_write_transaction(
        self, transaction_function, database: Optional[str] = None
    ):
        """Execute a write transaction."""
        with self.session(database) as session:
            return session.execute_write(transaction_function)

    def execute_read_transaction(
        self, transaction_function, database: Optional[str] = None
    ):
        """Execute a read transaction."""
        with self.session(database) as session:
            return session.execute_read(transaction_function)

    def create_indexes(self):
        """Create necessary indexes for performance."""
        indexes = [
            # Document indexes
            "CREATE INDEX document_id IF NOT EXISTS FOR (d:Document) ON (d.id)",
            "CREATE INDEX document_repo IF NOT EXISTS FOR (d:Document) ON (d.repository_id)",
            "CREATE INDEX document_path IF NOT EXISTS FOR (d:Document) ON (d.file_path)",
            # Reference indexes
            "CREATE INDEX reference_id IF NOT EXISTS FOR (r:Reference) ON (r.id)",
            "CREATE INDEX reference_type IF NOT EXISTS FOR (r:Reference) ON (r.type)",
            # Section indexes
            "CREATE INDEX section_id IF NOT EXISTS FOR (s:Section) ON (s.id)",
            "CREATE INDEX section_doc IF NOT EXISTS FOR (s:Section) ON (s.document_id)",
            # Unique constraints
            "CREATE CONSTRAINT unique_document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT unique_reference_id IF NOT EXISTS FOR (r:Reference) REQUIRE r.id IS UNIQUE",
        ]

        for index_query in indexes:
            try:
                self.execute_query(index_query)
                logger.info(f"Created index: {index_query.split(' ')[2]}")
            except Exception as e:
                logger.warning(f"Index creation warning: {str(e)}")

    def clear_database(self):
        """Clear all nodes and relationships (use with caution!)."""
        if settings.debug:  # Only allow in debug mode
            self.execute_query("MATCH (n) DETACH DELETE n")
            logger.warning("Neo4j database cleared")
        else:
            logger.error("Database clear attempted in production mode - rejected")
            raise PermissionError("Cannot clear database in production mode")

    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics."""
        stats = {}

        # Count nodes by label
        node_labels = ["Document", "Reference", "Section", "Repository"]
        for label in node_labels:
            result = self.execute_query(f"MATCH (n:{label}) RETURN count(n) as count")
            stats[f"{label.lower()}_count"] = result[0]["count"] if result else 0

        # Count relationships
        relationship_types = ["REFERENCES", "CONTAINS", "DEPENDS_ON", "RELATED_TO"]
        for rel_type in relationship_types:
            result = self.execute_query(
                f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
            )
            stats[f"{rel_type.lower()}_count"] = result[0]["count"] if result else 0

        return stats


# Global Neo4j connection instance
neo4j_config = Neo4jConfig()
neo4j_connection = Neo4jConnection(neo4j_config)
