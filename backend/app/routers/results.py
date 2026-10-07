from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..db import get_session
from ..dependencies import get_current_user, require_student, require_teacher
from ..grading import grade_quiz
from ..models import Course, Enrollment, Quiz, QuizAttempt, User, generate_id
from ..schemas import (
    CourseStudentResult,
    QuizAttemptCreateRequest,
    QuizAttemptResponse,
)

router = APIRouter(tags=["Results & Attempts"])


def attempt_to_response(
    attempt: QuizAttempt,
    student_name: str = "",
    course_title: str = "",
    quiz_title: str = "",
) -> QuizAttemptResponse:
    ts_ms = int(attempt.submitted_at.replace(tzinfo=timezone.utc).timestamp() * 1000)
    return QuizAttemptResponse(
        id=attempt.id,
        student_id=attempt.student_id,
        student_name=student_name or (attempt.student.name if attempt.student else attempt.student_id),
        course_id=attempt.course_id,
        course_title=course_title or (attempt.course.title if attempt.course else attempt.course_id),
        quiz_id=attempt.quiz_id,
        quiz_title=quiz_title or (attempt.quiz.title if attempt.quiz else attempt.quiz_id),
        score=attempt.score,
        total=attempt.total,
        percent=attempt.percent,
        answers=attempt.answers,
        submitted_at=attempt.submitted_at,
        timestamp=ts_ms,
    )


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=QuizAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_quiz_attempt(
    quiz_id: str,
    data: QuizAttemptCreateRequest,
    current_user: User = Depends(require_student),
    session: Session = Depends(get_session),
) -> QuizAttemptResponse:
    """Grade and record a student's quiz attempt (Student only)."""
    quiz = session.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    course = session.get(Course, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent course not found")

    # Verify student is enrolled in the parent course
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.course_id == quiz.course_id,
            Enrollment.student_id == current_user.id,
            Enrollment.status == "enrolled",
        )
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be an enrolled student in this course to take this quiz",
        )

    try:
        score, total, percent = grade_quiz(quiz.questions, data.answers)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    attempt = QuizAttempt(
        id=generate_id("res"),
        student_id=current_user.id,
        course_id=quiz.course_id,
        quiz_id=quiz.id,
        score=score,
        total=total,
        percent=percent,
        submitted_at=datetime.now(timezone.utc),
    )
    attempt.answers = data.answers

    session.add(attempt)
    session.commit()
    session.refresh(attempt)

    return attempt_to_response(
        attempt,
        student_name=current_user.name,
        course_title=course.title,
        quiz_title=quiz.title,
    )


@router.get(
    "/students/{student_id}/results",
    response_model=List[QuizAttemptResponse],
    status_code=status.HTTP_200_OK,
)
def get_student_results(
    student_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> List[QuizAttemptResponse]:
    """Get all quiz attempts for a student (Self or Teacher)."""
    if current_user.role != "teacher" and current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own results unless you are a teacher",
        )

    student = session.get(User, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    attempts = session.exec(
        select(QuizAttempt)
        .where(QuizAttempt.student_id == student_id)
        .order_by(QuizAttempt.submitted_at.desc())
    ).all()

    results = []
    for att in attempts:
        course = session.get(Course, att.course_id)
        quiz = session.get(Quiz, att.quiz_id)
        results.append(
            attempt_to_response(
                att,
                student_name=student.name,
                course_title=course.title if course else att.course_id,
                quiz_title=quiz.title if quiz else att.quiz_id,
            )
        )

    return results


@router.get(
    "/courses/{course_id}/results",
    response_model=List[CourseStudentResult],
    status_code=status.HTTP_200_OK,
)
def get_course_results(
    course_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> List[CourseStudentResult]:
    """Get quiz results breakdown for all enrolled students in a course (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    enrollments = session.exec(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.status == "enrolled",
        )
    ).all()

    student_results = []
    for enr in enrollments:
        student = session.get(User, enr.student_id)
        if not student:
            continue

        attempts = session.exec(
            select(QuizAttempt)
            .where(
                QuizAttempt.course_id == course_id,
                QuizAttempt.student_id == student.id,
            )
            .order_by(QuizAttempt.submitted_at.asc())
        ).all()

        attempt_responses = []
        for att in attempts:
            quiz = session.get(Quiz, att.quiz_id)
            attempt_responses.append(
                attempt_to_response(
                    att,
                    student_name=student.name,
                    course_title=course.title,
                    quiz_title=quiz.title if quiz else att.quiz_id,
                )
            )

        avg_percent = (
            round(sum(a.percent for a in attempts) / len(attempts))
            if attempts
            else None
        )
        last_percent = attempts[-1].percent if attempts else None

        student_results.append(
            CourseStudentResult(
                student_id=student.id,
                student_name=student.name,
                attempts=attempt_responses,
                avg_percent=avg_percent,
                last_percent=last_percent,
            )
        )

    return student_results
