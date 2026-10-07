from fastapi.testclient import TestClient
from backend.app.models import User


def test_full_quiz_attempt_and_results_flow(
    teacher_client: TestClient,
    student_client: TestClient,
    student_user: User,
    student_user_2: User,
    client: TestClient,
):
    # 1. Teacher creates course
    c_res = teacher_client.post("/courses", json={"title": "Computer Architecture", "description": "CPUs and Memory"})
    course_id = c_res.json()["id"]

    # 2. Teacher adds quiz
    q_res = teacher_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "title": "CPU Pipeline Quiz",
            "questions": [
                {
                    "text": "What does ALU stand for?",
                    "options": ["Arithmetic Logic Unit", "All Logic Unified", "Array Linear Unit", "Analog Line Unit"],
                    "correct_index": 0,
                },
                {
                    "text": "Which memory is fastest?",
                    "options": ["RAM", "SSD", "L1 Cache", "Hard Drive"],
                    "correct_index": 2,
                },
            ],
        },
    )
    quiz_id = q_res.json()["id"]
    q1_id = q_res.json()["questions"][0]["id"]
    q2_id = q_res.json()["questions"][1]["id"]

    # 3. Student tries to submit quiz before enrolling -> 403
    unauth_sub = student_client.post(
        f"/quizzes/{quiz_id}/attempts",
        json={"answers": {q1_id: 0, q2_id: 2}},
    )
    assert unauth_sub.status_code == 403

    # 4. Student enrolls and teacher approves
    student_client.post(f"/courses/{course_id}/enrollment-requests")
    teacher_client.post(f"/courses/{course_id}/enrollment-requests/{student_user.id}/approve")

    # 5. Student submits attempt 1 (1 out of 2 correct = 50%)
    att1_res = student_client.post(
        f"/quizzes/{quiz_id}/attempts",
        json={"answers": {q1_id: 0, q2_id: 0}},  # q1 correct (0), q2 wrong (0 != 2)
    )
    assert att1_res.status_code == 201
    att1 = att1_res.json()
    assert att1["score"] == 1
    assert att1["total"] == 2
    assert att1["percent"] == 50

    # 6. Student retakes quiz with perfect score (2 out of 2 = 100%)
    att2_res = student_client.post(
        f"/quizzes/{quiz_id}/attempts",
        json={"answers": {q1_id: 0, q2_id: 2}},
    )
    assert att2_res.status_code == 201
    att2 = att2_res.json()
    assert att2["score"] == 2
    assert att2["total"] == 2
    assert att2["percent"] == 100

    # 7. Student checks their own results
    my_results = student_client.get(f"/students/{student_user.id}/results").json()
    assert len(my_results) == 2
    scores = [r["score"] for r in my_results]
    assert 1 in scores and 2 in scores

    # 8. Another student tries to view this student's results -> 403
    other_client = client
    other_client.headers.update({"X-User-Id": student_user_2.id})
    forbidden_view = other_client.get(f"/students/{student_user.id}/results")
    assert forbidden_view.status_code == 403

    # 9. Teacher views course results ledger
    course_results = teacher_client.get(f"/courses/{course_id}/results").json()
    assert len(course_results) == 1
    student_entry = course_results[0]
    assert student_entry["student_id"] == student_user.id or student_entry["studentId"] == student_user.id
    assert len(student_entry["attempts"]) == 2
    # avg of 50 and 100 is 75
    assert student_entry["avg_percent"] == 75 or student_entry["avgPercent"] == 75
    # last attempt is 100
    assert student_entry["last_percent"] == 100 or student_entry["lastPercent"] == 100
