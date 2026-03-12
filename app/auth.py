"""
auth.py - Authentication Dependencies for FastAPI
Provides reusable dependencies to extract and validate the current user
from JWT tokens in request headers.
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import TokenData
from app.security import verify_token, is_token_blacklisted

# OAuth2PasswordBearer automatically extracts the token from
# the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Core dependency: Validates JWT token and returns the authenticated User.

    Steps:
    1. Extract token from Authorization header
    2. Check if token is blacklisted (logged out)
    3. Decode and verify JWT signature and expiry
    4. Look up user in database
    5. Ensure user account is active

    Raises HTTPException 401 if any step fails.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Step 2: Blacklist check (token revoked on logout)
    if is_token_blacklisted(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
        )

    # Step 3: Decode and verify JWT
    token_data: TokenData = verify_token(token, token_type="access")

    # Step 4: Fetch user from DB
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception

    # Step 5: Ensure account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that ensures the user is active.
    Wraps get_current_user for semantic clarity.
    """
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that restricts access to Admin role only.
    Use this on admin-only endpoints.

    Raises HTTPException 403 if user is not an admin.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User | None:
    """
    Optional authentication dependency.
    Returns the user if authenticated, None otherwise.
    Useful for endpoints that behave differently for authenticated users.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    try:
        if is_token_blacklisted(token, db):
            return None
        token_data = verify_token(token)
        user = db.query(User).filter(User.id == token_data.user_id).first()
        return user if user and user.is_active else None
    except Exception:
        return None
