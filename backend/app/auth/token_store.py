import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class TokenStore:
    """Simple file-based token storage for development"""

    def __init__(self, storage_path: str = "./tokens"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

    def store_credentials(self, user_id: str, credentials: Credentials) -> bool:
        """Store user credentials"""
        try:
            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": (
                    credentials.expiry.isoformat() if credentials.expiry else None
                ),
                "stored_at": datetime.utcnow().isoformat(),
            }

            token_file = self.storage_path / f"{user_id}.json"
            with open(token_file, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)

            logger.info(f"Stored credentials for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store credentials for user {user_id}: {str(e)}")
            return False

    def get_credentials(self, user_id: str) -> Optional[Credentials]:
        """Retrieve user credentials"""
        try:
            token_file = self.storage_path / f"{user_id}.json"
            if not token_file.exists():
                return None

            with open(token_file, "r", encoding="utf-8") as f:
                token_data = json.load(f)

            # Convert expiry back to datetime
            expiry = None
            if token_data.get("expiry"):
                expiry = datetime.fromisoformat(token_data["expiry"])

            credentials = Credentials(
                token=token_data["token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes"),
                expiry=expiry,
            )

            return credentials

        except Exception as e:
            logger.error(f"Failed to retrieve credentials for user {user_id}: {str(e)}")
            return None

    def delete_credentials(self, user_id: str) -> bool:
        """Delete stored credentials"""
        try:
            token_file = self.storage_path / f"{user_id}.json"
            if token_file.exists():
                token_file.unlink()
                logger.info(f"Deleted credentials for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete credentials for user {user_id}: {str(e)}")
            return False

    def refresh_credentials(self, user_id: str) -> Optional[Credentials]:
        """Refresh expired credentials"""
        try:
            credentials = self.get_credentials(user_id)
            if not credentials:
                return None

            if credentials.expired and credentials.refresh_token:
                from google.auth.transport.requests import Request

                credentials.refresh(Request())

                # Store refreshed credentials
                self.store_credentials(user_id, credentials)
                logger.info(f"Refreshed credentials for user {user_id}")

                return credentials

            return credentials

        except Exception as e:
            logger.error(f"Failed to refresh credentials for user {user_id}: {str(e)}")
            return None


# Global token store instance
token_store = TokenStore()
