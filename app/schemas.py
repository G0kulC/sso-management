"""
schemas.py - Pydantic Schemas for Request/Response Validation
Separates API contracts from database models for clean architecture
"""

from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List
from datetime import datetime
from app.models import UserRole


# ─────────────────────────────────────────────
# AUTH SCHEMAS
# ─────────────────────────────────────────────

class UserRegister(BaseModel):
    """Schema for user registration request"""
    username: str = Field(..., min_length=3, max_length=50, example="john_doe")
    email: EmailStr = Field(..., example="john@example.com")
    password: str = Field(..., min_length=8, example="SecurePass123!")
    full_name: Optional[str] = Field(None, max_length=100, example="John Doe")
    role: Optional[UserRole] = UserRole.USER

    @validator("username")
    def username_alphanumeric(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores/hyphens allowed)")
        return v.lower()


class UserLogin(BaseModel):
    """Schema for login request"""
    username: str = Field(..., example="john_doe")
    password: str = Field(..., example="SecurePass123!")


class Token(BaseModel):
    """Schema for token response after successful login"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int                # Seconds until access token expiry


class TokenRefresh(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str


class TokenData(BaseModel):
    """Schema for decoded JWT payload"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None


# ─────────────────────────────────────────────
# USER SCHEMAS
# ─────────────────────────────────────────────

class UserBase(BaseModel):
    """Shared fields between create/update"""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    """Schema for creating a user (includes password)"""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for partial user updates"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    """Schema for user data in API responses (no password)"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True   # Enable ORM mode


class UserListResponse(BaseModel):
    """Paginated list of users"""
    total: int
    users: List[UserResponse]


# ─────────────────────────────────────────────
# APPLICATION SCHEMAS
# ─────────────────────────────────────────────

class AppCreate(BaseModel):
    """Schema for registering a client application"""
    name: str = Field(..., min_length=2, max_length=100, example="My Web App")
    redirect_uri: str = Field(..., example="https://myapp.com/callback")
    description: Optional[str] = Field(None, max_length=500)


class AppResponse(BaseModel):
    """Schema for application data in responses"""
    id: int
    name: str
    client_id: str
    client_secret: str          # Shown ONCE at creation
    redirect_uri: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AppPublicResponse(BaseModel):
    """Public app info (no secret)"""
    id: int
    name: str
    client_id: str
    redirect_uri: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# SESSION & LOG SCHEMAS
# ─────────────────────────────────────────────

class SessionResponse(BaseModel):
    """Schema for session data"""
    id: int
    user_id: int
    is_revoked: bool
    expiry: datetime
    created_at: datetime
    ip_address: Optional[str]

    class Config:
        from_attributes = True


class LoginLogResponse(BaseModel):
    """Schema for audit log entries"""
    id: int
    user_id: Optional[int]
    username_attempted: Optional[str]
    login_time: datetime
    ip_address: Optional[str]
    success: bool
    failure_reason: Optional[str]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# SSO SCHEMAS
# ─────────────────────────────────────────────

class SSOTokenVerify(BaseModel):
    """Schema for client apps to verify SSO tokens"""
    token: str
    client_id: str
    client_secret: str


class SSOTokenResponse(BaseModel):
    """Response after token verification"""
    valid: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    message: str


# ─────────────────────────────────────────────
# GENERIC RESPONSE SCHEMAS
# ─────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


class ErrorResponse(BaseModel):
    """Generic error response"""
    detail: str
