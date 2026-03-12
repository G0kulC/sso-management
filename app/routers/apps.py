"""
routers/apps.py - Application Registration & SSO Endpoints
Manages client applications and SSO token verification flow
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Application, User
from app.schemas import (
    AppCreate, AppResponse, AppPublicResponse,
    SSOTokenVerify, SSOTokenResponse, MessageResponse
)
from app.auth import require_admin, get_current_user
from app.security import generate_client_credentials, verify_token, is_token_blacklisted

router = APIRouter(prefix="/apps", tags=["Application Management"])


@router.post("/register", response_model=AppResponse, status_code=201,
             summary="Register a client application (Admin only)")
def register_application(
    app_data: AppCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Register a new client application with the SSO server.
    **Requires Admin role.**

    Generates and returns a unique **client_id** and **client_secret**.
    Store the client_secret securely — it will not be shown again in plain form.

    The **redirect_uri** must exactly match when the client exchanges tokens.
    """
    # Check for duplicate app name
    existing = db.query(Application).filter(Application.name == app_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Application '{app_data.name}' is already registered"
        )

    # Generate cryptographically secure credentials
    client_id, client_secret = generate_client_credentials()

    app = Application(
        name=app_data.name,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=app_data.redirect_uri,
        description=app_data.description,
        created_by=admin.id,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    return app


@router.get("/", response_model=List[AppPublicResponse], summary="List registered applications")
def list_applications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)    # Any authenticated user
):
    """
    List all registered client applications.
    **Requires authentication.**

    Client secrets are NOT included in this response for security.
    """
    apps = db.query(Application).filter(
        Application.is_active == True
    ).offset(skip).limit(limit).all()
    return apps


@router.get("/{app_id}", response_model=AppPublicResponse, summary="Get application details")
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Retrieve details of a specific registered application."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {app_id} not found"
        )
    return app


@router.delete("/{app_id}", response_model=MessageResponse,
               summary="Delete/deactivate application (Admin only)")
def delete_application(
    app_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin)
):
    """
    Deactivate and remove a registered client application.
    **Requires Admin role.**

    This soft-deletes the application (marks as inactive).
    """
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {app_id} not found"
        )

    app_name = app.name
    db.delete(app)
    db.commit()

    return MessageResponse(message=f"Application '{app_name}' has been removed")


# ─────────────────────────────────────────────
# SSO VERIFICATION ENDPOINT
# ─────────────────────────────────────────────

@router.post("/verify-token", response_model=SSOTokenResponse,
             summary="Verify SSO token (for client applications)")
def verify_sso_token(
    payload: SSOTokenVerify,
    db: Session = Depends(get_db)
):
    """
    **SSO Token Verification Endpoint**

    Client applications use this to verify that a user's SSO token is valid.

    Flow:
    1. User logs in to SSO server → receives access_token
    2. User presents token to client application
    3. Client app calls this endpoint with token + its credentials
    4. SSO server validates token and returns user info
    5. Client app grants access based on the response

    The client must provide its **client_id** and **client_secret** for authentication.
    """
    # Step 1: Validate the client application credentials
    app = db.query(Application).filter(
        Application.client_id == payload.client_id,
        Application.client_secret == payload.client_secret,
        Application.is_active == True
    ).first()

    if not app:
        return SSOTokenResponse(
            valid=False,
            message="Invalid client credentials or application not registered"
        )

    # Step 2: Check token blacklist
    if is_token_blacklisted(payload.token, db):
        return SSOTokenResponse(
            valid=False,
            message="Token has been revoked"
        )

    # Step 3: Verify JWT signature and expiry
    try:
        token_data = verify_token(payload.token, token_type="access")
    except Exception:
        return SSOTokenResponse(
            valid=False,
            message="Token is invalid or expired"
        )

    # Step 4: Confirm user still exists and is active
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user or not user.is_active:
        return SSOTokenResponse(
            valid=False,
            message="Associated user not found or account disabled"
        )

    return SSOTokenResponse(
        valid=True,
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        message="Token is valid"
    )
