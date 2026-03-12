"""
routers/auth.py - Authentication Endpoints
Handles registration, login, logout, and token refresh
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Session as UserSession, LoginLog, TokenBlacklist
from app.schemas import (
    UserRegister, UserLogin, Token, TokenRefresh,
    UserResponse, MessageResponse
)
from app.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    verify_token, blacklist_token, is_token_blacklisted
)
from app.auth import get_current_user, oauth2_scheme
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _log_attempt(db: Session, user_id, username, ip, ua, success, reason=None):
    """Helper to write a login audit log entry"""
    log = LoginLog(
        user_id=user_id,
        username_attempted=username,
        ip_address=ip,
        user_agent=ua,
        success=success,
        failure_reason=reason,
    )
    db.add(log)
    db.commit()


@router.post("/register", response_model=UserResponse, status_code=201,
             summary="Register a new user account")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Create a new user account.

    - Validates that username and email are unique
    - Hashes password with bcrypt before storing
    - Default role is 'user'; admins can be created manually
    """
    # Check username uniqueness
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{user_data.username}' is already taken"
        )

    # Check email uniqueness
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{user_data.email}' is already registered"
        )

    # Create user with hashed password
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token, summary="Login and receive JWT tokens")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate with username + password (OAuth2 Password Flow).

    Returns:
    - **access_token**: Short-lived JWT (30 min) for API access
    - **refresh_token**: Long-lived JWT (7 days) to get new access tokens
    - **token_type**: "bearer"

    All login attempts (success/failure) are recorded in login_logs.
    """
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")

    # Look up user
    user = db.query(User).filter(User.username == form_data.username).first()

    # Validate credentials
    if not user or not verify_password(form_data.password, user.password_hash):
        _log_attempt(db, None, form_data.username, ip, ua, False, "Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        _log_attempt(db, user.id, user.username, ip, ua, False, "Account disabled")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact an administrator."
        )

    # Build token payload
    token_payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
    }

    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)

    # Calculate expiry for session record
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Store session record
    session = UserSession(
        user_id=user.id,
        token=access_token,
        refresh_token=refresh_token,
        expiry=expiry,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(session)

    # Log successful login
    _log_attempt(db, user.id, user.username, ip, ua, True)
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse, summary="Logout and revoke tokens")
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Invalidate the current access token by adding it to the blacklist.

    After logout:
    - The access token is added to TokenBlacklist table
    - The session record is marked as revoked
    - Subsequent requests with the same token will be rejected
    """
    # Decode to get expiry for cleanup scheduling
    from app.security import decode_token_raw
    payload = decode_token_raw(token)
    exp_ts = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else datetime.now(timezone.utc)

    # Add to blacklist
    if not is_token_blacklisted(token, db):
        blacklist_token(token, expires_at, db)

    # Revoke session record
    session = db.query(UserSession).filter(
        UserSession.token == token,
        UserSession.user_id == current_user.id
    ).first()
    if session:
        session.is_revoked = True
        db.commit()

    return MessageResponse(message="Successfully logged out")


@router.post("/refresh", response_model=Token, summary="Get new access token using refresh token")
def refresh_token(
    body: TokenRefresh,
    db: Session = Depends(get_db)
):
    """
    Exchange a valid refresh token for a new access token + refresh token pair.

    - Verifies the refresh token is valid and not blacklisted
    - Issues a new access token (rotating refresh tokens for security)
    """
    # Verify it's a valid refresh token
    token_data = verify_token(body.refresh_token, token_type="refresh")

    if is_token_blacklisted(body.refresh_token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked"
        )

    # Confirm user still exists and is active
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account disabled"
        )

    # Blacklist old refresh token (rotation)
    from app.security import decode_token_raw
    payload = decode_token_raw(body.refresh_token)
    exp_ts = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else datetime.now(timezone.utc)
    blacklist_token(body.refresh_token, expires_at, db)

    # Issue new token pair
    token_payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
    }
    new_access = create_access_token(token_payload)
    new_refresh = create_refresh_token(token_payload)

    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    session = UserSession(user_id=user.id, token=new_access, refresh_token=new_refresh, expiry=expiry)
    db.add(session)
    db.commit()

    return Token(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse, summary="Get current authenticated user")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated user."""
    return current_user
