from fastapi.testclient import TestClient
from backend.app.models import User


def test_enrollment_request_and_approval_flow(
    teacher_client: TestClient,
    student_client: TestClient,
    student_user: User,
):
    # 1. Teacher creates course
    c_res = teacher_client.post("/courses", json={"title": "Data Structures", "description": "Trees and graphs"})
    course_id = c_res.json()["id"]

    # 2. Student requests to join
    req_res = student_client.post(f"/courses/{course_id}/enrollment-requests")
    assert req_res.status_code == 201
    assert req_res.json()["status"] == "pending"

    # 3. Duplicate request returns 409 Conflict
    dup_res = student_client.post(f"/courses/{course_id}/enrollment-requests")
    assert dup_res.status_code == 409

    # 4. Teacher checks roster
    roster_res = teacher_client.get(f"/courses/{course_id}/roster")
    assert roster_res.status_code == 200
    roster = roster_res.json()
    assert len(roster["pending"]) == 1
    assert roster["pending"][0]["id"] == student_user.id
    assert len(roster["enrolled"]) == 0

    # 5. Teacher approves student
    appr_res = teacher_client.post(f"/courses/{course_id}/enrollment-requests/{student_user.id}/approve")
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "enrolled"

    # 6. Roster now reflects enrolled student
    roster_res2 = teacher_client.get(f"/courses/{course_id}/roster")
    roster2 = roster_res2.json()
    assert len(roster2["pending"]) == 0
    assert len(roster2["enrolled"]) == 1
    assert roster2["enrolled"][0]["id"] == student_user.id


def test_decline_and_re_request_flow(
    teacher_client: TestClient,
    student_client: TestClient,
    student_user: User,
):
    # 1. Course created
    c_res = teacher_client.post("/courses", json={"title": "Economics 101", "description": "Microeconomics"})
    course_id = c_res.json()["id"]

    # 2. Student requests
    student_client.post(f"/courses/{course_id}/enrollment-requests")

    # 3. Teacher declines
    dec_res = teacher_client.post(f"/courses/{course_id}/enrollment-requests/{student_user.id}/decline")
    assert dec_res.status_code == 204

    # 4. Roster is empty
    roster = teacher_client.get(f"/courses/{course_id}/roster").json()
    assert len(roster["pending"]) == 0
    assert len(roster["enrolled"]) == 0

    # 5. Student re-requests successfully
    re_req = student_client.post(f"/courses/{course_id}/enrollment-requests")
    assert re_req.status_code == 201
    assert re_req.json()["status"] == "pending"


def test_remove_enrolled_student(
    teacher_client: TestClient,
    student_client: TestClient,
    student_user: User,
):
    c_res = teacher_client.post("/courses", json={"title": "Organic Chemistry", "description": ""})
    course_id = c_res.json()["id"]

    student_client.post(f"/courses/{course_id}/enrollment-requests")
    teacher_client.post(f"/courses/{course_id}/enrollment-requests/{student_user.id}/approve")

    del_res = teacher_client.delete(f"/courses/{course_id}/students/{student_user.id}")
    assert del_res.status_code == 204

    roster = teacher_client.get(f"/courses/{course_id}/roster").json()
    assert len(roster["enrolled"]) == 0


def test_student_cannot_approve_requests(
    teacher_client: TestClient,
    student_client: TestClient,
    student_user: User,
):
    c_res = teacher_client.post("/courses", json={"title": "Philosophy", "description": "Ethics"})
    course_id = c_res.json()["id"]

    student_client.post(f"/courses/{course_id}/enrollment-requests")
    unauth_appr = student_client.post(f"/courses/{course_id}/enrollment-requests/{student_user.id}/approve")
    assert unauth_appr.status_code == 403
