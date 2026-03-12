"""
routers/users.py - User Management Endpoints
CRUD operations for user accounts with RBAC enforcement
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import User, LoginLog
from app.schemas import (
    UserResponse, UserUpdate, UserListResponse,
    LoginLogResponse, MessageResponse
)
from app.auth import get_current_user, require_admin
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("/", response_model=UserListResponse, summary="List all users (Admin only)")
def list_users(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
    role: Optional[str] = Query(None, description="Filter by role: admin or user"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin)     # Enforces admin-only access
):
    """
    Retrieve a paginated list of all registered users.
    **Requires Admin role.**

    Supports filtering by role and active status.
    """
    query = db.query(User)

    # Apply optional filters
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return UserListResponse(total=total, users=users)


@router.get("/logs", response_model=List[LoginLogResponse],
            summary="View login audit logs (Admin only)")
def get_login_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None, description="Filter logs by user ID"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin)
):
    """
    Retrieve login audit logs for security monitoring.
    **Requires Admin role.**

    Shows all login attempts (successes and failures) with IP addresses.
    """
    query = db.query(LoginLog)
    if user_id:
        query = query.filter(LoginLog.user_id == user_id)

    logs = query.order_by(LoginLog.login_time.desc()).offset(skip).limit(limit).all()
    return logs


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a specific user's profile by their ID.

    - **Admins** can view any user's profile
    - **Regular users** can only view their own profile
    """
    # RBAC: Users can only see themselves; admins can see anyone
    from app.models import UserRole
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse, summary="Update user profile")
def update_user(
    user_id: int,
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a user's profile information.

    - **Users** can update their own email, full_name, and password
    - **Admins** can update any user including changing roles and active status
    - Role changes are restricted to admin users only
    """
    from app.models import UserRole

    # Permission check
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )

    # Role changes require admin
    if update_data.role is not None and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    # Apply updates (only provided fields)
    if update_data.email is not None:
        # Check email uniqueness
        existing = db.query(User).filter(
            User.email == update_data.email, User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use by another account"
            )
        user.email = update_data.email

    if update_data.full_name is not None:
        user.full_name = update_data.full_name

    if update_data.password is not None:
        user.password_hash = hash_password(update_data.password)

    if update_data.role is not None:
        user.role = update_data.role

    if update_data.is_active is not None:
        user.is_active = update_data.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=MessageResponse,
               summary="Delete user account (Admin only)")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Permanently delete a user account and all associated data.
    **Requires Admin role.**

    Note: Cascade deletion removes sessions and login logs as well.
    Admins cannot delete their own account via this endpoint.
    """
    # Prevent self-deletion
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot delete their own account"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    username = user.username
    db.delete(user)
    db.commit()

    return MessageResponse(message=f"User '{username}' has been permanently deleted")
