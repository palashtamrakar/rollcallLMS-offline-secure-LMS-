from fastapi.testclient import TestClient


def test_create_course_as_teacher(teacher_client: TestClient):
    response = teacher_client.post(
        "/courses",
        json={"title": "Introduction to Algorithms", "description": "Graph theory, sorting, and dynamic programming."},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Introduction to Algorithms"
    assert data["description"] == "Graph theory, sorting, and dynamic programming."
    assert data["teacher_id"].startswith("teacher-") or data["teacherId"].startswith("teacher-")


def test_student_cannot_create_course(student_client: TestClient):
    response = student_client.post(
        "/courses",
        json={"title": "Unauthorized Course", "description": "Should fail"},
    )
    assert response.status_code == 403


def test_list_courses(teacher_client: TestClient, client: TestClient):
    teacher_client.post("/courses", json={"title": "Physics 101", "description": "Mechanics"})
    teacher_client.post("/courses", json={"title": "Chemistry 101", "description": "Thermodynamics"})

    response = client.get("/courses")
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 2
    titles = [c["title"] for c in courses]
    assert "Physics 101" in titles
    assert "Chemistry 101" in titles


def test_get_course_detail(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Calculus I", "description": "Limits and derivatives"})
    course_id = c_res.json()["id"]

    res = teacher_client.get(f"/courses/{course_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == course_id
    assert data["title"] == "Calculus I"
    assert isinstance(data["videos"], list)
    assert isinstance(data["quizzes"], list)


def test_delete_course_cascades(teacher_client: TestClient, student_client: TestClient):
    # 1. Create course
    c_res = teacher_client.post("/courses", json={"title": "Biology", "description": "Cell biology"})
    course_id = c_res.json()["id"]

    # 2. Add video
    teacher_client.post(
        f"/courses/{course_id}/videos",
        json={"title": "Intro Video", "youtube_url": "https://youtu.be/dQw4w9WgXcQ"},
    )

    # 3. Add quiz
    teacher_client.post(
        f"/courses/{course_id}/quizzes",
        json={
            "title": "Bio Quiz 1",
            "questions": [
                {"text": "What is DNA?", "options": ["Protein", "Nucleic acid"], "correct_index": 1}
            ],
        },
    )

    # 4. Request enrollment
    student_client.post(f"/courses/{course_id}/enrollment-requests")

    # 5. Delete course
    del_res = teacher_client.delete(f"/courses/{course_id}")
    assert del_res.status_code == 204

    # 6. Verify course is deleted
    get_res = teacher_client.get(f"/courses/{course_id}")
    assert get_res.status_code == 404


def test_update_course_as_teacher(teacher_client: TestClient):
    # 1. Create course
    c_res = teacher_client.post("/courses", json={"title": "Linear Algebra", "description": "Vectors and matrices"})
    course_id = c_res.json()["id"]

    # 2. Update both title and description
    put_res = teacher_client.put(
        f"/courses/{course_id}",
        json={"title": "Linear Algebra & Applications", "description": "Eigenvalues, SVD, and PCA"},
    )
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["title"] == "Linear Algebra & Applications"
    assert data["description"] == "Eigenvalues, SVD, and PCA"

    # 3. Verify via GET
    get_res = teacher_client.get(f"/courses/{course_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Linear Algebra & Applications"
    assert get_res.json()["description"] == "Eigenvalues, SVD, and PCA"


def test_update_course_title_only(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "History 101", "description": "Ancient civilizations"})
    course_id = c_res.json()["id"]

    patch_res = teacher_client.patch(
        f"/courses/{course_id}",
        json={"title": "World History 101"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["title"] == "World History 101"
    assert data["description"] == "Ancient civilizations"


def test_update_course_description_only(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Chemistry 102", "description": "Old description"})
    course_id = c_res.json()["id"]

    put_res = teacher_client.put(
        f"/courses/{course_id}",
        json={"description": "Updated thermodynamics and equilibrium."},
    )
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["title"] == "Chemistry 102"
    assert data["description"] == "Updated thermodynamics and equilibrium."


def test_update_course_empty_title_validation(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Valid Title", "description": "Desc"})
    course_id = c_res.json()["id"]

    res = teacher_client.put(f"/courses/{course_id}", json={"title": "   "})
    assert res.status_code == 422


def test_student_cannot_update_course(student_client: TestClient, teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Literature", "description": "Poetry"})
    course_id = c_res.json()["id"]

    res = student_client.put(f"/courses/{course_id}", json={"title": "Hacked Course Name"})
    assert res.status_code == 403


def test_unauthenticated_cannot_update_course(client: TestClient, teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Art History", "description": "Renaissance"})
    course_id = c_res.json()["id"]

    res = client.put(f"/courses/{course_id}", json={"title": "Hacked Title"})
    assert res.status_code == 401


def test_update_nonexistent_course(teacher_client: TestClient):
    res = teacher_client.put("/courses/course-nonexistent", json={"title": "Ghost Course"})
    assert res.status_code == 404

