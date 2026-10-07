from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from .db import get_session
from .models import User


def get_current_user_optional(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    session: Session = Depends(get_session),
) -> Optional[User]:
    if not x_user_id:
        return None
    user = session.exec(select(User).where(User.id == x_user_id)).first()
    return user


def get_current_user(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    session: Session = Depends(get_session),
) -> User:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing X-User-Id header",
        )
    user = session.exec(select(User).where(User.id == x_user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User with id '{x_user_id}' not found",
        )
    return user


def require_teacher(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires a teacher persona",
        )
    return current_user


def require_student(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires a student persona",
        )
    return current_user
