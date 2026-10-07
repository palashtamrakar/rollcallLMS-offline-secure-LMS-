import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models import User


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="teacher_user")
def teacher_user_fixture(session: Session) -> User:
    teacher = User(id="teacher-test1", name="Prof. Turing", role="teacher")
    session.add(teacher)
    session.commit()
    session.refresh(teacher)
    return teacher


@pytest.fixture(name="student_user")
def student_user_fixture(session: Session) -> User:
    student = User(id="student-test1", name="Ada Lovelace", role="student")
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


@pytest.fixture(name="student_user_2")
def student_user_2_fixture(session: Session) -> User:
    student = User(id="student-test2", name="Grace Hopper", role="student")
    session.add(student)
    session.commit()
    session.refresh(student)
    return student


@pytest.fixture(name="teacher_client")
def teacher_client_fixture(session: Session, teacher_user: User):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app, headers={"X-User-Id": teacher_user.id}) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="student_client")
def student_client_fixture(session: Session, student_user: User):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app, headers={"X-User-Id": student_user.id}) as client:
        yield client
    app.dependency_overrides.clear()
