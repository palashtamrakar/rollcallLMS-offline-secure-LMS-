import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from ..db import PRESENTATIONS_DIR, UPLOAD_DIR, get_session
from ..dependencies import get_current_user_optional, require_teacher
from ..models import Course, Quiz, User, generate_id
from ..schemas import (
    CourseCreateRequest,
    CourseDetailResponse,
    CourseSummaryResponse,
    CourseUpdateRequest,
    PresentationResponse,
    QuestionResponse,
    QuizResponse,
    VideoResponse,
)
from .presentations import build_presentation_response
from .videos import build_video_response

router = APIRouter(prefix="/courses", tags=["Courses"])


def build_quiz_response(quiz: Quiz, is_teacher: bool) -> QuizResponse:
    q_responses = []
    for q in quiz.questions:
        q_responses.append(
            QuestionResponse(
                id=q.id,
                quiz_id=q.quiz_id,
                text=q.text,
                options=q.options,
                correct_index=q.correct_index if is_teacher else None,
            )
        )
    return QuizResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        title=quiz.title,
        questions=q_responses,
    )


def build_course_summary(course: Course, is_teacher: bool) -> CourseSummaryResponse:
    enrolled_ids = [e.student_id for e in course.enrollments if e.status == "enrolled"]
    pending_ids = [e.student_id for e in course.enrollments if e.status == "pending"]
    v_responses = [build_video_response(v) for v in course.videos]
    p_responses = [build_presentation_response(p) for p in (course.presentations or [])]
    q_responses = [build_quiz_response(q, is_teacher) for q in course.quizzes]

    return CourseSummaryResponse(
        id=course.id,
        title=course.title,
        description=course.description,
        teacher_id=course.teacher_id,
        video_count=len(course.videos),
        presentation_count=len(course.presentations or []),
        quiz_count=len(course.quizzes),
        enrolled_count=len(enrolled_ids),
        pending_count=len(pending_ids),
        enrolled=enrolled_ids,
        pending=pending_ids,
        videos=v_responses,
        presentations=p_responses,
        quizzes=q_responses,
    )


def build_course_detail(course: Course, is_teacher: bool) -> CourseDetailResponse:
    enrolled_ids = [e.student_id for e in course.enrollments if e.status == "enrolled"]
    pending_ids = [e.student_id for e in course.enrollments if e.status == "pending"]
    v_responses = [build_video_response(v) for v in course.videos]
    p_responses = [build_presentation_response(p) for p in (course.presentations or [])]
    q_responses = [build_quiz_response(q, is_teacher) for q in course.quizzes]

    return CourseDetailResponse(
        id=course.id,
        title=course.title,
        description=course.description,
        teacher_id=course.teacher_id,
        video_count=len(course.videos),
        presentation_count=len(course.presentations or []),
        quiz_count=len(course.quizzes),
        enrolled_count=len(enrolled_ids),
        pending_count=len(pending_ids),
        videos=v_responses,
        presentations=p_responses,
        quizzes=q_responses,
        enrolled=enrolled_ids,
        pending=pending_ids,
    )



@router.get("", response_model=List[CourseSummaryResponse])
def list_courses(
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: Session = Depends(get_session),
) -> List[CourseSummaryResponse]:
    """
    List all courses.
    Includes counts and lists of enrolled/pending students.
    Questions redact correct_index unless requester is a teacher.
    """
    is_teacher = current_user.role == "teacher" if current_user else False
    courses = session.exec(select(Course).order_by(Course.id)).all()
    return [build_course_summary(c, is_teacher) for c in courses]


@router.get("/{course_id}", response_model=CourseDetailResponse)
def get_course(
    course_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: Session = Depends(get_session),
) -> CourseDetailResponse:
    """
    Get full details for a course including its videos and quizzes.
    Questions redact correct_index unless requester is a teacher.
    """
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    is_teacher = current_user.role == "teacher" if current_user else False
    return build_course_detail(course, is_teacher)


@router.post("", response_model=CourseSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    data: CourseCreateRequest,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> CourseSummaryResponse:
    """Create a new course (Teacher only)."""
    course = Course(
        id=generate_id("course"),
        title=data.title,
        description=data.description,
        teacher_id=current_user.id,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    return build_course_summary(course, is_teacher=True)


@router.put("/{course_id}", response_model=CourseSummaryResponse)
@router.patch("/{course_id}", response_model=CourseSummaryResponse)
@router.post("/{course_id}", response_model=CourseSummaryResponse)
@router.post("/{course_id}/update", response_model=CourseSummaryResponse)
def update_course(
    course_id: str,
    data: CourseUpdateRequest,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> CourseSummaryResponse:
    """Update a course title and/or description (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if data.title is not None:
        course.title = data.title
    if data.description is not None:
        course.description = data.description

    session.add(course)
    session.commit()
    session.refresh(course)
    return build_course_summary(course, is_teacher=True)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> Response:
    """Delete a course and cascade to videos, quizzes, enrollments, and attempts (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Clean up local video files from disk
    for v in course.videos:
        if v.video_type == "local":
            if v.file_path:
                Path(v.file_path).unlink(missing_ok=True)
            if v.file_name:
                (UPLOAD_DIR / v.file_name).unlink(missing_ok=True)

    # Clean up local presentation files and extracted images from disk
    for p in (course.presentations or []):
        if p.presentation_type == "local":
            if p.file_path:
                Path(p.file_path).unlink(missing_ok=True)
            if p.file_name:
                (PRESENTATIONS_DIR / p.file_name).unlink(missing_ok=True)
            pres_folder = PRESENTATIONS_DIR / p.id
            if pres_folder.exists() and pres_folder.is_dir():
                shutil.rmtree(pres_folder, ignore_errors=True)

    session.delete(course)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

