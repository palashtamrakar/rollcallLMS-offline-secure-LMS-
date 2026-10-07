from fastapi.testclient import TestClient


def test_login_creates_new_user(client: TestClient):
    response = client.post(
        "/auth/login",
        json={"name": "Marie Curie", "role": "teacher"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Marie Curie"
    assert data["role"] == "teacher"
    assert data["id"].startswith("teacher-")


def test_login_returns_existing_user(client: TestClient):
    # First login
    res1 = client.post(
        "/auth/login",
        json={"name": "Albert Einstein", "role": "student"},
    )
    assert res1.status_code == 200
    user1 = res1.json()

    # Second login with exact same credentials
    res2 = client.post(
        "/auth/login",
        json={"name": "Albert Einstein", "role": "student"},
    )
    assert res2.status_code == 200
    user2 = res2.json()

    assert user1["id"] == user2["id"]
    assert user1["name"] == user2["name"]
    assert user1["role"] == user2["role"]


def test_login_different_role_creates_separate_user(client: TestClient):
    res1 = client.post("/auth/login", json={"name": "Jordan", "role": "teacher"})
    res2 = client.post("/auth/login", json={"name": "Jordan", "role": "student"})

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["id"] != res2.json()["id"]


def test_auth_me_endpoint(client: TestClient, teacher_user):
    # Without header -> 401
    res_unauth = client.get("/auth/me")
    assert res_unauth.status_code == 401

    # With valid header
    res_auth = client.get("/auth/me", headers={"X-User-Id": teacher_user.id})
    assert res_auth.status_code == 200
    assert res_auth.json()["id"] == teacher_user.id
    assert res_auth.json()["name"] == teacher_user.name
