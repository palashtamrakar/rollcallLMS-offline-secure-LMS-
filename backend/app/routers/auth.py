from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select

from ..db import get_session
from ..dependencies import get_current_user
from ..models import User, generate_id
from ..schemas import UserLoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=UserResponse, status_code=status.HTTP_200_OK)
def login(data: UserLoginRequest, session: Session = Depends(get_session)) -> User:
    """
    Find or create a user by (name, role).
    Preserves continuous history across logins with the same name and persona.
    """
    user = session.exec(
        select(User).where(User.name == data.name, User.role == data.role)
    ).first()

    if not user:
        user = User(
            id=generate_id(data.role),
            name=data.name,
            role=data.role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    return user


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retrieve the currently authenticated user based on X-User-Id header."""
    return current_user
