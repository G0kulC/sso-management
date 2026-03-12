"""
security.py - Core Security Utilities
Handles password hashing, JWT creation/verification, and token management
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.schemas import TokenData

# ─────────────────────────────────────────────
# PASSWORD HASHING
# ─────────────────────────────────────────────

# CryptContext uses bcrypt with automatic cost factor tuning
# bcrypt is the industry standard for password storage
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    bcrypt automatically generates a salt and applies ~12 rounds by default.
    bcrypt has a 72-byte password limit, so we truncate if necessary.
    """
    # Truncate to 72 bytes to comply with bcrypt's limit
    password_bytes = password.encode('utf-8')[:72]
    password_truncated = password_bytes.decode('utf-8', errors='ignore')
    return pwd_context.hash(password_truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.
    Returns True if they match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ─────────────────────────────────────────────
# JWT TOKEN MANAGEMENT
# ─────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload dict (must include 'sub', 'username', 'role')
        expires_delta: Custom expiry; defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES

    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),   # Issued At
        "type": "access"                      # Token type claim
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """
    Create a long-lived JWT refresh token (7 days by default).
    Refresh tokens can be exchanged for new access tokens.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"                     # Distinguish from access tokens
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> TokenData:
    """
    Decode and verify a JWT token.

    Args:
        token: The raw JWT string
        token_type: 'access' or 'refresh'

    Returns:
        TokenData with user info extracted from payload

    Raises:
        HTTPException 401 if token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # Validate token type matches expected
        if payload.get("type") != token_type:
            raise credentials_exception

        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")

        if user_id is None:
            raise credentials_exception

        return TokenData(user_id=int(user_id), username=username, role=role)

    except JWTError:
        raise credentials_exception


def decode_token_raw(token: str) -> dict:
    """
    Decode JWT without verification (for inspection only).
    Never use this for authentication decisions.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return {}


# ─────────────────────────────────────────────
# TOKEN BLACKLIST UTILITIES
# ─────────────────────────────────────────────

def is_token_blacklisted(token: str, db: Session) -> bool:
    """
    Check if a token has been revoked (blacklisted on logout).

    Args:
        token: The JWT string to check
        db: Active database session

    Returns:
        True if blacklisted, False if valid
    """
    from app.models import TokenBlacklist
    record = db.query(TokenBlacklist).filter(
        TokenBlacklist.token == token
    ).first()
    return record is not None


def blacklist_token(token: str, expires_at: datetime, db: Session) -> None:
    """
    Add a token to the blacklist (called on logout).

    Args:
        token: JWT string to revoke
        expires_at: When the token naturally expires (for cleanup)
        db: Active database session
    """
    from app.models import TokenBlacklist
    entry = TokenBlacklist(token=token, expires_at=expires_at)
    db.add(entry)
    db.commit()


def generate_client_credentials() -> tuple[str, str]:
    """
    Generate a random client_id and client_secret for application registration.
    Returns: (client_id, client_secret)
    """
    import secrets
    client_id = secrets.token_hex(16)       # 32-char hex string
    client_secret = secrets.token_hex(32)   # 64-char hex string
    return client_id, client_secret
