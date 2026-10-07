import json
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from ..db import get_session
from ..dependencies import require_teacher
from ..models import Course, Question, Quiz, generate_id
from ..schemas import QuestionResponse, QuizCreateRequest, QuizResponse

router = APIRouter(prefix="/courses/{course_id}/quizzes", tags=["Quizzes"])


@router.post("", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def create_quiz(
    course_id: str,
    data: QuizCreateRequest,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> QuizResponse:
    """Create a new quiz with questions for a course (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    quiz = Quiz(
        id=generate_id("quiz"),
        course_id=course_id,
        title=data.title,
    )
    session.add(quiz)
    session.flush()

    question_responses = []
    for q_data in data.questions:
        question = Question(
            id=generate_id("q"),
            quiz_id=quiz.id,
            text=q_data.text,
            options_json=json.dumps(q_data.options),
            correct_index=q_data.correct_index,
        )
        session.add(question)
        question_responses.append(
            QuestionResponse(
                id=question.id,
                quiz_id=quiz.id,
                text=question.text,
                options=q_data.options,
                correct_index=question.correct_index,
            )
        )

    session.commit()
    session.refresh(quiz)

    return QuizResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        title=quiz.title,
        questions=question_responses,
    )


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(
    course_id: str,
    quiz_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> Response:
    """Delete a quiz from a course (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    quiz = session.get(Quiz, quiz_id)
    if not quiz or quiz.course_id != course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found in this course")

    session.delete(quiz)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
