from typing import Optional

from app.auth.oauth import GoogleOAuthHandler, JWTHandler
from app.auth.token_store import token_store
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth_handler = GoogleOAuthHandler()
jwt_handler = JWTHandler()
security = HTTPBearer()


@router.get("/login")
async def login(redirect_url: Optional[str] = Query(None)):
    """Initiate Google OAuth login"""
    authorization_url = oauth_handler.get_authorization_url(state=redirect_url)
    return {"authorization_url": authorization_url}


@router.get("/callback")
async def auth_callback(code: str, state: Optional[str] = None):
    """Handle Google OAuth callback"""
    try:
        token_data = oauth_handler.exchange_code_for_token(code, state)
        user_info = token_data["user_info"]

        # Create JWT token with user info
        jwt_payload = {
            "user_id": user_info["id"],
            "email": user_info["email"],
            "name": user_info["name"],
            "picture": user_info.get("picture", ""),
        }

        access_token = jwt_handler.create_access_token(jwt_payload)

        # Store OAuth credentials for API access
        token_store.store_credentials(user_info["id"], token_data["credentials"])

        # If state parameter exists, redirect to that URL
        if state:
            return RedirectResponse(url=f"{state}?token={access_token}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_info": user_info,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@router.get("/me")
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get current authenticated user info"""
    token = credentials.credentials
    payload = jwt_handler.verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
    }


@router.post("/logout")
async def logout():
    """Logout user (client-side token removal)"""
    return {
        "message": "Logged out successfully. Please remove the token from client storage."
    }


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Dependency to get current user ID from JWT token"""
    token = credentials.credentials
    payload = jwt_handler.verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload.get("user_id")
