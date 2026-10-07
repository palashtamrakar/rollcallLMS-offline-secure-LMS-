from fastapi.testclient import TestClient


def test_create_quiz_success(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "World History", "description": "Ancient civilizations"})
    course_id = c_res.json()["id"]

    q_res = teacher_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "title": "Mesopotamia Quiz",
            "questions": [
                {
                    "text": "Which rivers bordered Mesopotamia?",
                    "options": ["Nile & Amazon", "Tigris & Euphrates", "Indus & Ganges", "Danube & Rhine"],
                    "correct_index": 1,
                },
                {
                    "text": "What script was invented in Sumer?",
                    "options": ["Hieroglyphics", "Latin", "Cuneiform", "Linear B"],
                    "correct_index": 2,
                },
            ],
        },
    )
    assert q_res.status_code == 201
    data = q_res.json()
    assert data["title"] == "Mesopotamia Quiz"
    assert len(data["questions"]) == 2
    assert data["questions"][0]["options"][1] == "Tigris & Euphrates"


def test_quiz_redacts_correct_index_for_student(
    teacher_client: TestClient, student_client: TestClient, client: TestClient
):
    c_res = teacher_client.post("/courses", json={"title": "Computer Networks", "description": "Protocols"})
    course_id = c_res.json()["id"]

    teacher_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "title": "OSI Model Quiz",
            "questions": [
                {
                    "text": "How many layers in the OSI model?",
                    "options": ["4", "5", "7", "9"],
                    "correct_index": 2,
                }
            ],
        },
    )

    # 1. Teacher view includes correct_index
    t_view = teacher_client.get(f"/courses/{course_id}").json()
    assert t_view["quizzes"][0]["questions"][0]["correctIndex"] == 2 or t_view["quizzes"][0]["questions"][0].get("correct_index") == 2

    # 2. Student view completely redacts correct_index
    s_view = student_client.get(f"/courses/{course_id}").json()
    q_student = s_view["quizzes"][0]["questions"][0]
    assert q_student.get("correct_index") is None and q_student.get("correctIndex") is None

    # 3. Public/unauthenticated view also redacts correct_index
    pub_view = client.get(f"/courses/{course_id}").json()
    q_pub = pub_view["quizzes"][0]["questions"][0]
    assert q_pub.get("correct_index") is None and q_pub.get("correctIndex") is None


def test_create_quiz_invalid_validation(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Validation Test", "description": ""})
    course_id = c_res.json()["id"]

    # 1. Question with only 1 option
    bad_res1 = teacher_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "title": "Bad Quiz",
            "questions": [{"text": "Q1", "options": ["Only one"], "correct_index": 0}],
        },
    )
    assert bad_res1.status_code == 422

    # 2. Invalid correct_index out of bounds
    bad_res2 = teacher_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "title": "Bad Quiz",
            "questions": [{"text": "Q1", "options": ["Opt A", "Opt B"], "correct_index": 5}],
        },
    )
    assert bad_res2.status_code == 422


def test_delete_quiz(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Art History", "description": "Renaissance"})
    course_id = c_res.json()["id"]

    q_res = teacher_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "title": "Renaissance Quiz",
            "questions": [{"text": "Who painted Mona Lisa?", "options": ["Da Vinci", "Michelangelo"], "correct_index": 0}],
        },
    )
    quiz_id = q_res.json()["id"]

    del_res = teacher_client.delete(f"/courses/{course_id}/quizzes/{quiz_id}")
    assert del_res.status_code == 204

    c_detail = teacher_client.get(f"/courses/{course_id}").json()
    assert len(c_detail["quizzes"]) == 0
