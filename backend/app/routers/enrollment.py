from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from ..db import get_session
from ..dependencies import require_student, require_teacher
from ..models import Course, Enrollment, User, generate_id
from ..schemas import EnrollmentResponse, RosterResponse, UserResponse

router = APIRouter(prefix="/courses/{course_id}", tags=["Enrollment"])


@router.post(
    "/enrollment-requests",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_enrollment(
    course_id: str,
    current_user: User = Depends(require_student),
    session: Session = Depends(get_session),
) -> EnrollmentResponse:
    """Request enrollment into a course (Student only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    existing = session.exec(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == current_user.id,
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Enrollment already exists with status '{existing.status}'",
        )

    enrollment = Enrollment(
        id=generate_id("enr"),
        course_id=course_id,
        student_id=current_user.id,
        status="pending",
    )
    session.add(enrollment)
    session.commit()
    session.refresh(enrollment)
    return EnrollmentResponse(
        id=enrollment.id,
        course_id=enrollment.course_id,
        student_id=enrollment.student_id,
        status=enrollment.status,
    )


@router.post(
    "/enrollment-requests/{student_id}/approve",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_200_OK,
)
def approve_enrollment(
    course_id: str,
    student_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> EnrollmentResponse:
    """Approve a student's pending enrollment request (Teacher only)."""
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == student_id,
            Enrollment.status == "pending",
        )
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending enrollment request not found",
        )

    enrollment.status = "enrolled"
    session.add(enrollment)
    session.commit()
    session.refresh(enrollment)
    return EnrollmentResponse(
        id=enrollment.id,
        course_id=enrollment.course_id,
        student_id=enrollment.student_id,
        status=enrollment.status,
    )


@router.post(
    "/enrollment-requests/{student_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
)
def decline_enrollment(
    course_id: str,
    student_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> Response:
    """Decline and remove a pending enrollment request (Teacher only)."""
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == student_id,
            Enrollment.status == "pending",
        )
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending enrollment request not found",
        )

    session.delete(enrollment)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_enrolled_student(
    course_id: str,
    student_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> Response:
    """Remove an enrolled student from a course (Teacher only)."""
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.student_id == student_id,
            Enrollment.status == "enrolled",
        )
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrolled student not found in this course",
        )

    session.delete(enrollment)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/roster",
    response_model=RosterResponse,
    status_code=status.HTTP_200_OK,
)
def get_course_roster(
    course_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> RosterResponse:
    """Get pending and enrolled students for a course (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    enrollments = session.exec(
        select(Enrollment).where(Enrollment.course_id == course_id)
    ).all()

    pending_users = []
    enrolled_users = []

    for enr in enrollments:
        student = session.get(User, enr.student_id)
        if not student:
            continue
        user_resp = UserResponse(id=student.id, name=student.name, role=student.role)
        if enr.status == "pending":
            pending_users.append(user_resp)
        elif enr.status == "enrolled":
            enrolled_users.append(user_resp)

    return RosterResponse(pending=pending_users, enrolled=enrolled_users)
