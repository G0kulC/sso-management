"""
models.py - SQLAlchemy ORM Models
Defines the database schema for all entities in the SSO system
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    """Enumeration for user roles in RBAC"""
    ADMIN = "admin"
    USER = "user"


class User(Base):
    """
    User Model - Core identity entity.
    Stores credentials, role, and profile information.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)             # bcrypt hash
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    login_logs = relationship("LoginLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role}>"


class Application(Base):
    """
    Application Model - Represents client apps registered with the SSO.
    Each app has a unique client_id/client_secret pair for OAuth2-like flow.
    """
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    client_id = Column(String(64), unique=True, nullable=False, index=True)
    client_secret = Column(String(128), nullable=False)             # Hashed in production
    redirect_uri = Column(Text, nullable=False)                    # Allowed callback URLs
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Application id={self.id} name={self.name} client_id={self.client_id}>"


class Session(Base):
    """
    Session Model - Tracks active user sessions.
    Used for token blacklisting on logout.
    """
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(Text, nullable=False, unique=True)               # JWT access token
    refresh_token = Column(Text, nullable=True, unique=True)        # Refresh token
    is_revoked = Column(Boolean, default=False, nullable=False)     # Blacklist flag
    expiry = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)                  # IPv4/IPv6
    user_agent = Column(Text, nullable=True)

    # Relationship back to User
    user = relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<Session id={self.id} user_id={self.user_id} revoked={self.is_revoked}>"


class LoginLog(Base):
    """
    LoginLog Model - Audit trail for all authentication events.
    Records login attempts (success/failure) for security monitoring.
    """
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null on failed attempt
    username_attempted = Column(String(50), nullable=True)             # Track failed usernames
    login_time = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String(255), nullable=True)               # Why login failed

    # Relationship back to User
    user = relationship("User", back_populates="login_logs")

    def __repr__(self):
        return f"<LoginLog id={self.id} user_id={self.user_id} success={self.success}>"


class TokenBlacklist(Base):
    """
    TokenBlacklist Model - Stores revoked JWT tokens.
    Ensures logged-out tokens cannot be reused.
    """
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    token = Column(Text, nullable=False, unique=True)
    blacklisted_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<TokenBlacklist id={self.id}>"
