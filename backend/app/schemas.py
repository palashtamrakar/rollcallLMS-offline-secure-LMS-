from datetime import datetime, timezone
from typing import Any, List, Literal, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, field_validator


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


# --- User / Auth ---
class UserLoginRequest(BaseSchema):
    name: str = Field(..., min_length=1)
    role: Literal["teacher", "student"]

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class UserResponse(BaseSchema):
    id: str
    name: str
    role: str


def parse_time_to_seconds(val: Any) -> float:
    """Parse integer, float, or timestamp string (MM:SS, HH:MM:SS, SS) to total seconds."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return 0.0
        try:
            return float(val)
        except ValueError:
            pass
        parts = val.split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 1:
                return float(parts[0])
        except ValueError:
            pass
    return 0.0


def format_seconds_to_timestamp(seconds: float) -> str:
    """Format total seconds to friendly MM:SS or HH:MM:SS string."""
    secs = int(round(seconds))
    hours = secs // 3600
    mins = (secs % 3600) // 60
    rem_secs = secs % 60
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{rem_secs:02d}"
    return f"{mins:02d}:{rem_secs:02d}"


class VideoChunk(BaseSchema):
    start: float = Field(default=0.0, description="Start time in seconds")
    end: float = Field(default=0.0, description="End time in seconds")
    title: Optional[str] = Field(default="", description="Optional chunk/segment title")

    @field_validator("start", "end", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> float:
        return parse_time_to_seconds(v)

    @computed_field
    @property
    def startFormatted(self) -> str:
        return format_seconds_to_timestamp(self.start)

    @computed_field
    @property
    def endFormatted(self) -> str:
        return format_seconds_to_timestamp(self.end)


# --- Videos ---
class VideoCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1)
    youtube_url: str = Field(
        ...,
        validation_alias=AliasChoices("youtube_url", "youtubeUrl", "url"),
        min_length=1,
    )
    chunks: Optional[List[VideoChunk]] = Field(default_factory=list)

    @field_validator("title", "youtube_url")
    @classmethod
    def strip_fields(cls, v: str) -> str:
        return v.strip()


class VideoResponse(BaseSchema):
    id: str
    course_id: str
    title: str
    video_type: str = "youtube"
    youtube_id: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    url: Optional[str] = None
    chunks: List[VideoChunk] = Field(default_factory=list)

    @computed_field
    @property
    def courseId(self) -> str:
        return self.course_id

    @computed_field
    @property
    def videoType(self) -> str:
        return self.video_type

    @computed_field
    @property
    def youtubeId(self) -> Optional[str]:
        return self.youtube_id

    @computed_field
    @property
    def fileName(self) -> Optional[str]:
        return self.file_name

    @computed_field
    @property
    def filePath(self) -> Optional[str]:
        return self.file_path

    @computed_field
    @property
    def contentType(self) -> Optional[str]:
        return self.content_type

    @computed_field
    @property
    def fileSize(self) -> Optional[int]:
        return self.file_size




# --- Presentations ---
class SlideTextBlock(BaseSchema):
    text: str
    level: int = 0
    is_bold: bool = False
    is_title: bool = False

    @computed_field
    @property
    def isBold(self) -> bool:
        return self.is_bold

    @computed_field
    @property
    def isTitle(self) -> bool:
        return self.is_title


class SlideTable(BaseSchema):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class SlideImage(BaseSchema):
    url: str
    filename: str
    content_type: Optional[str] = None

    @computed_field
    @property
    def contentType(self) -> Optional[str]:
        return self.content_type


class SlideData(BaseSchema):
    index: int
    title: str = ""
    notes: Optional[str] = None
    video_id: Optional[str] = None
    video_start: Optional[float] = None
    video_end: Optional[float] = None
    text_blocks: List[SlideTextBlock] = Field(default_factory=list)
    tables: List[SlideTable] = Field(default_factory=list)
    images: List[SlideImage] = Field(default_factory=list)

    @computed_field
    @property
    def textBlocks(self) -> List[SlideTextBlock]:
        return self.text_blocks

    @computed_field
    @property
    def videoId(self) -> Optional[str]:
        return self.video_id

    @computed_field
    @property
    def videoStart(self) -> Optional[float]:
        return self.video_start

    @computed_field
    @property
    def videoEnd(self) -> Optional[float]:
        return self.video_end


class SlideMappingItem(BaseSchema):
    slide_index: int = Field(..., validation_alias=AliasChoices("slide_index", "slideIndex", "index"))
    video_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("video_id", "videoId"))
    video_start: Optional[float] = Field(default=None, validation_alias=AliasChoices("video_start", "videoStart", "start"))
    video_end: Optional[float] = Field(default=None, validation_alias=AliasChoices("video_end", "videoEnd", "end"))


class SlideMappingUpdateRequest(BaseSchema):
    mappings: List[SlideMappingItem] = Field(default_factory=list)


class PresentationCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1)
    description: Optional[str] = Field(default="")
    embed_url: str = Field(
        ...,
        validation_alias=AliasChoices("embed_url", "embedUrl", "url"),
        min_length=1,
    )

    @field_validator("title", "embed_url")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class PresentationResponse(BaseSchema):
    id: str
    course_id: str
    title: str
    description: Optional[str] = ""
    presentation_type: str = "local"
    embed_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    slide_count: int = 0
    download_url: Optional[str] = None
    slides: List[SlideData] = Field(default_factory=list)

    @computed_field
    @property
    def courseId(self) -> str:
        return self.course_id

    @computed_field
    @property
    def presentationType(self) -> str:
        return self.presentation_type

    @computed_field
    @property
    def embedUrl(self) -> Optional[str]:
        return self.embed_url

    @computed_field
    @property
    def fileName(self) -> Optional[str]:
        return self.file_name

    @computed_field
    @property
    def fileSize(self) -> Optional[int]:
        return self.file_size

    @computed_field
    @property
    def slideCount(self) -> int:
        return self.slide_count

    @computed_field
    @property
    def downloadUrl(self) -> Optional[str]:
        return self.download_url


# --- Questions & Quizzes ---
class QuestionCreate(BaseSchema):
    text: str = Field(..., min_length=1)
    options: List[str]
    correct_index: int = Field(
        ...,
        validation_alias=AliasChoices("correct_index", "correctIndex", "correct"),
    )

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: List[str]) -> List[str]:
        cleaned = [opt.strip() for opt in v]
        if len(cleaned) < 2:
            raise ValueError("Every question must have at least 2 options")
        if any(not opt for opt in cleaned):
            raise ValueError("Options cannot be blank")
        return cleaned

    @field_validator("correct_index")
    @classmethod
    def validate_correct_index(cls, v: int, info) -> int:
        options = info.data.get("options")
        if options is not None:
            if v < 0 or v >= len(options):
                raise ValueError(f"correct_index must be between 0 and {len(options) - 1}")
        return v


class QuestionResponse(BaseSchema):
    id: str
    quiz_id: str
    text: str
    options: List[str]
    correct_index: Optional[int] = None

    @computed_field
    @property
    def quizId(self) -> str:
        return self.quiz_id

    @computed_field
    @property
    def correctIndex(self) -> Optional[int]:
        return self.correct_index


class QuizCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1)
    questions: List[QuestionCreate]

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Quiz title cannot be empty")
        return v

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v: List[QuestionCreate]) -> List[QuestionCreate]:
        if not v:
            raise ValueError("A quiz must have at least one question")
        return v


class QuizResponse(BaseSchema):
    id: str
    course_id: str
    title: str
    questions: List[QuestionResponse] = []

    @computed_field
    @property
    def courseId(self) -> str:
        return self.course_id


# --- Courses ---
class CourseCreateRequest(BaseSchema):
    title: str = Field(..., min_length=1)
    description: str = Field(default="")

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Course title cannot be empty")
        return v


class CourseUpdateRequest(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Course title cannot be empty")
        return v


class CourseSummaryResponse(BaseSchema):
    id: str
    title: str
    description: str = ""
    teacher_id: str
    video_count: int = 0
    presentation_count: int = 0
    quiz_count: int = 0
    enrolled_count: int = 0
    pending_count: int = 0
    enrolled: List[str] = []
    pending: List[str] = []
    videos: List[VideoResponse] = []
    presentations: List[PresentationResponse] = []
    quizzes: List[QuizResponse] = []

    @computed_field
    @property
    def teacherId(self) -> str:
        return self.teacher_id

    @computed_field
    @property
    def videoCount(self) -> int:
        return self.video_count

    @computed_field
    @property
    def presentationCount(self) -> int:
        return self.presentation_count

    @computed_field
    @property
    def quizCount(self) -> int:
        return self.quiz_count

    @computed_field
    @property
    def enrolledCount(self) -> int:
        return self.enrolled_count

    @computed_field
    @property
    def pendingCount(self) -> int:
        return self.pending_count


class CourseDetailResponse(BaseSchema):
    id: str
    title: str
    description: str = ""
    teacher_id: str
    video_count: int = 0
    presentation_count: int = 0
    quiz_count: int = 0
    enrolled_count: int = 0
    pending_count: int = 0
    videos: List[VideoResponse] = []
    presentations: List[PresentationResponse] = []
    quizzes: List[QuizResponse] = []
    enrolled: List[str] = []
    pending: List[str] = []

    @computed_field
    @property
    def teacherId(self) -> str:
        return self.teacher_id

    @computed_field
    @property
    def videoCount(self) -> int:
        return self.video_count or len(self.videos)

    @computed_field
    @property
    def presentationCount(self) -> int:
        return self.presentation_count or len(self.presentations)

    @computed_field
    @property
    def quizCount(self) -> int:
        return self.quiz_count or len(self.quizzes)

    @computed_field
    @property
    def enrolledCount(self) -> int:
        return self.enrolled_count or len(self.enrolled)

    @computed_field
    @property
    def pendingCount(self) -> int:
        return self.pending_count or len(self.pending)


# --- Enrollment ---
class EnrollmentResponse(BaseSchema):
    id: str
    course_id: str
    student_id: str
    status: str

    @computed_field
    @property
    def courseId(self) -> str:
        return self.course_id

    @computed_field
    @property
    def studentId(self) -> str:
        return self.student_id


class RosterResponse(BaseSchema):
    pending: List[UserResponse] = []
    enrolled: List[UserResponse] = []


# --- Quiz Attempts / Results ---
class QuizAttemptCreateRequest(BaseSchema):
    answers: dict[str, int]


class QuizAttemptResponse(BaseSchema):
    id: str
    student_id: str
    student_name: str
    course_id: str
    course_title: str
    quiz_id: str
    quiz_title: str
    score: int
    total: int
    percent: int
    answers: dict[str, int] = {}
    submitted_at: datetime
    timestamp: int

    @computed_field
    @property
    def studentId(self) -> str:
        return self.student_id

    @computed_field
    @property
    def studentName(self) -> str:
        return self.student_name

    @computed_field
    @property
    def courseId(self) -> str:
        return self.course_id

    @computed_field
    @property
    def courseTitle(self) -> str:
        return self.course_title

    @computed_field
    @property
    def quizId(self) -> str:
        return self.quiz_id

    @computed_field
    @property
    def quizTitle(self) -> str:
        return self.quiz_title

    @computed_field
    @property
    def submittedAt(self) -> datetime:
        return self.submitted_at


class CourseStudentResult(BaseSchema):
    student_id: str
    student_name: str
    attempts: List[QuizAttemptResponse] = []
    avg_percent: Optional[int] = None
    last_percent: Optional[int] = None

    @computed_field
    @property
    def studentId(self) -> str:
        return self.student_id

    @computed_field
    @property
    def studentName(self) -> str:
        return self.student_name

    @computed_field
    @property
    def avgPercent(self) -> Optional[int]:
        return self.avg_percent

    @computed_field
    @property
    def lastPercent(self) -> Optional[int]:
        return self.last_percent
