import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


def generate_id(prefix: str) -> str:
    """Generate client-compatible friendly IDs like 'teacher-x7k2p9q' or 'course-a1b2c3d'."""
    suffix = uuid.uuid4().hex[:7]
    return f"{prefix}-{suffix}"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: generate_id("user"), primary_key=True)
    name: str = Field(index=True)
    role: str = Field(index=True)  # 'teacher' | 'student'

    enrollments: List["Enrollment"] = Relationship(back_populates="student", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    attempts: List["QuizAttempt"] = Relationship(back_populates="student", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Course(SQLModel, table=True):
    __tablename__ = "courses"

    id: str = Field(default_factory=lambda: generate_id("course"), primary_key=True)
    title: str = Field(index=True)
    description: str = Field(default="")
    teacher_id: str = Field(foreign_key="users.id", index=True)

    videos: List["Video"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Video.id"},
    )
    presentations: List["Presentation"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Presentation.id"},
    )
    quizzes: List["Quiz"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Quiz.id"},
    )
    enrollments: List["Enrollment"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    attempts: List["QuizAttempt"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Video(SQLModel, table=True):
    __tablename__ = "videos"

    id: str = Field(default_factory=lambda: generate_id("vid"), primary_key=True)
    course_id: str = Field(foreign_key="courses.id", index=True)
    title: str
    video_type: str = Field(default="youtube", index=True)  # 'youtube' | 'local'
    youtube_id: Optional[str] = Field(default=None, nullable=True)
    file_path: Optional[str] = Field(default=None, nullable=True)
    file_name: Optional[str] = Field(default=None, nullable=True)
    content_type: Optional[str] = Field(default=None, nullable=True)
    file_size: Optional[int] = Field(default=None, nullable=True)
    chunks_json: str = Field(default="[]")

    course: Optional[Course] = Relationship(back_populates="videos")

    @property
    def chunks(self) -> list[dict]:
        try:
            return json.loads(self.chunks_json) if self.chunks_json else []
        except Exception:
            return []

    @chunks.setter
    def chunks(self, val: list[dict]) -> None:
        self.chunks_json = json.dumps(val) if val else "[]"


class Presentation(SQLModel, table=True):
    __tablename__ = "presentations"

    id: str = Field(default_factory=lambda: generate_id("pres"), primary_key=True)
    course_id: str = Field(foreign_key="courses.id", index=True)
    title: str
    description: Optional[str] = Field(default="", nullable=True)
    presentation_type: str = Field(default="local", index=True)  # 'local' | 'embed'
    embed_url: Optional[str] = Field(default=None, nullable=True)
    file_path: Optional[str] = Field(default=None, nullable=True)
    file_name: Optional[str] = Field(default=None, nullable=True)
    file_size: Optional[int] = Field(default=None, nullable=True)
    content_type: Optional[str] = Field(default=None, nullable=True)
    slide_count: int = Field(default=0)
    slides_json: str = Field(default="[]")

    course: Optional[Course] = Relationship(back_populates="presentations")

    @property
    def slides(self) -> list[dict]:
        try:
            return json.loads(self.slides_json) if self.slides_json else []
        except Exception:
            return []

    @slides.setter
    def slides(self, val: list[dict]) -> None:
        self.slides_json = json.dumps(val) if val else "[]"




class Quiz(SQLModel, table=True):
    __tablename__ = "quizzes"

    id: str = Field(default_factory=lambda: generate_id("quiz"), primary_key=True)
    course_id: str = Field(foreign_key="courses.id", index=True)
    title: str

    course: Optional[Course] = Relationship(back_populates="quizzes")
    questions: List["Question"] = Relationship(
        back_populates="quiz",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Question.id"},
    )
    attempts: List["QuizAttempt"] = Relationship(
        back_populates="quiz",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Question(SQLModel, table=True):
    __tablename__ = "questions"

    id: str = Field(default_factory=lambda: generate_id("q"), primary_key=True)
    quiz_id: str = Field(foreign_key="quizzes.id", index=True)
    text: str
    options_json: str = Field(default="[]")
    correct_index: int

    quiz: Optional[Quiz] = Relationship(back_populates="questions")

    @property
    def options(self) -> list[str]:
        try:
            return json.loads(self.options_json)
        except Exception:
            return []

    @options.setter
    def options(self, val: list[str]) -> None:
        self.options_json = json.dumps(val)


class Enrollment(SQLModel, table=True):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_course_student_enrollment"),)

    id: str = Field(default_factory=lambda: generate_id("enr"), primary_key=True)
    course_id: str = Field(foreign_key="courses.id", index=True)
    student_id: str = Field(foreign_key="users.id", index=True)
    status: str = Field(default="pending")  # 'pending' | 'enrolled'

    course: Optional[Course] = Relationship(back_populates="enrollments")
    student: Optional[User] = Relationship(back_populates="enrollments")


class QuizAttempt(SQLModel, table=True):
    __tablename__ = "quiz_attempts"

    id: str = Field(default_factory=lambda: generate_id("res"), primary_key=True)
    student_id: str = Field(foreign_key="users.id", index=True)
    course_id: str = Field(foreign_key="courses.id", index=True)
    quiz_id: str = Field(foreign_key="quizzes.id", index=True)
    score: int
    total: int
    percent: int
    answers_json: str = Field(default="{}")
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    student: Optional[User] = Relationship(back_populates="attempts")
    course: Optional[Course] = Relationship(back_populates="attempts")
    quiz: Optional[Quiz] = Relationship(back_populates="attempts")

    @property
    def answers(self) -> dict[str, int]:
        try:
            return json.loads(self.answers_json)
        except Exception:
            return {}

    @answers.setter
    def answers(self, val: dict[str, int]) -> None:
        self.answers_json = json.dumps(val)
