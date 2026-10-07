import io
import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.db import UPLOAD_DIR



def test_add_video_success(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Linear Algebra", "description": "Vectors and matrices"})
    course_id = c_res.json()["id"]

    v_res = teacher_client.post(
        f"/courses/{course_id}/videos",
        json={"title": "Lecture 1: Intro", "youtube_url": "https://www.youtube.com/watch?v=fNk_zzaMoSs"},
    )
    assert v_res.status_code == 201
    data = v_res.json()
    assert data["title"] == "Lecture 1: Intro"
    assert data["youtube_id"] == "fNk_zzaMoSs" or data["youtubeId"] == "fNk_zzaMoSs"
    assert data["video_type"] == "youtube" or data["videoType"] == "youtube"


def test_add_video_invalid_url_rejected(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Discrete Math", "description": "Logic"})
    course_id = c_res.json()["id"]

    v_res = teacher_client.post(
        f"/courses/{course_id}/videos",
        json={"title": "Broken Link", "youtube_url": "https://not-youtube.com/watch?v=123"},
    )
    assert v_res.status_code == 400
    assert "Couldn't read a YouTube video id" in v_res.json()["detail"]


def test_upload_local_video_with_custom_title(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Data Structures", "description": "Trees and Graphs"})
    course_id = c_res.json()["id"]

    fake_video_content = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41" + b"A" * 1024
    files = {"file": ("binary_trees.mp4", io.BytesIO(fake_video_content), "video/mp4")}
    data = {"title": "Lecture 4: Binary Search Trees"}

    res = teacher_client.post(
        f"/courses/{course_id}/videos/upload",
        files=files,
        data=data,
    )
    assert res.status_code == 201
    v_data = res.json()
    assert v_data["title"] == "Lecture 4: Binary Search Trees"
    assert v_data["video_type"] == "local" or v_data["videoType"] == "local"
    assert v_data["file_name"] or v_data["fileName"]
    assert v_data["url"].endswith(f"/api/videos/{v_data['id']}/stream")

    # Verify stream endpoint returns the video
    stream_res = teacher_client.get(f"/videos/{v_data['id']}/stream")
    assert stream_res.status_code == 200
    assert stream_res.content == fake_video_content


def test_upload_local_video_auto_title_from_filename(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Database Systems", "description": "SQL and NoSQL"})
    course_id = c_res.json()["id"]

    fake_video_content = b"\x1aE\xdf\xa3" + b"WebM data" * 100
    files = {"file": ("relational_algebra_intro.webm", io.BytesIO(fake_video_content), "video/webm")}

    res = teacher_client.post(
        f"/courses/{course_id}/videos/upload",
        files=files,
    )
    assert res.status_code == 201
    v_data = res.json()
    assert v_data["title"] == "relational algebra intro"
    assert v_data["video_type"] == "local" or v_data["videoType"] == "local"


def test_upload_local_video_rejects_invalid_extension(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Security 101", "description": "Cybersecurity"})
    course_id = c_res.json()["id"]

    files = {"file": ("malicious.exe", io.BytesIO(b"executable content"), "application/x-msdownload")}
    res = teacher_client.post(
        f"/courses/{course_id}/videos/upload",
        files=files,
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]


def test_upload_local_video_rejects_empty_file(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Networking", "description": "TCP/IP"})
    course_id = c_res.json()["id"]

    files = {"file": ("empty.mp4", io.BytesIO(b""), "video/mp4")}
    res = teacher_client.post(
        f"/courses/{course_id}/videos/upload",
        files=files,
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"]


def test_stream_range_requests(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Operating Systems", "description": "Kernel and Memory"})
    course_id = c_res.json()["id"]

    fake_video_content = b"0123456789" * 100  # 1000 bytes
    files = {"file": ("paging.mp4", io.BytesIO(fake_video_content), "video/mp4")}
    res = teacher_client.post(
        f"/courses/{course_id}/videos/upload",
        files=files,
    )
    vid_id = res.json()["id"]

    # Request first 100 bytes via Range header
    range_res = teacher_client.get(f"/videos/{vid_id}/stream", headers={"Range": "bytes=0-99"})
    assert range_res.status_code == 206
    assert len(range_res.content) == 100
    assert range_res.content == fake_video_content[:100]


def test_remove_video_and_disk_cleanup(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Astronomy", "description": "Stars"})
    course_id = c_res.json()["id"]

    # 1. YouTube video removal
    v_res = teacher_client.post(
        f"/courses/{course_id}/videos",
        json={"title": "Telescopes", "youtube_url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    vid_id = v_res.json()["id"]

    del_res = teacher_client.delete(f"/courses/{course_id}/videos/{vid_id}")
    assert del_res.status_code == 204

    # 2. Local video upload and removal with disk cleanup
    fake_video = b"test video data for cleanup"
    upload_res = teacher_client.post(
        f"/courses/{course_id}/videos/upload",
        files={"file": ("planets.mp4", io.BytesIO(fake_video), "video/mp4")},
    )
    local_vid = upload_res.json()
    local_vid_id = local_vid["id"]
    file_name = local_vid["fileName"] or local_vid["file_name"]
    saved_file_path = UPLOAD_DIR / file_name
    assert saved_file_path.exists()

    del_local_res = teacher_client.delete(f"/courses/{course_id}/videos/{local_vid_id}")
    assert del_local_res.status_code == 204
    # File should be removed from disk
    assert not saved_file_path.exists()

    # Verify course now has 0 videos
    c_detail = teacher_client.get(f"/courses/{course_id}").json()
    assert len(c_detail["videos"]) == 0


def test_upload_local_video_with_chunks(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Data Structures", "description": "Trees and Graphs"})
    course_id = c_res.json()["id"]

    fake_video = b"test video data for chunks"
    chunks_payload = json.dumps([
        {"start": "00:30", "end": "00:32", "title": "Definition"},
        {"start": "0:55", "end": "0:59", "title": "Traversals"}
    ])

    res = teacher_client.post(
        f"/courses/{course_id}/videos/upload",
        files={"file": ("trees.mp4", io.BytesIO(fake_video), "video/mp4")},
        data={"title": "Binary Tree Concepts", "chunks": chunks_payload},
    )
    assert res.status_code == 201
    v_data = res.json()
    assert len(v_data["chunks"]) == 2
    assert v_data["chunks"][0]["start"] == 30.0
    assert v_data["chunks"][0]["end"] == 32.0
    assert v_data["chunks"][0]["title"] == "Definition"
    assert v_data["chunks"][0]["startFormatted"] == "00:30"
    assert v_data["chunks"][0]["endFormatted"] == "00:32"

    assert v_data["chunks"][1]["start"] == 55.0
    assert v_data["chunks"][1]["end"] == 59.0
    assert v_data["chunks"][1]["title"] == "Traversals"


def test_add_youtube_video_with_chunks(teacher_client: TestClient):
    c_res = teacher_client.post("/courses", json={"title": "Web Dev", "description": "Frontend and Backend"})
    course_id = c_res.json()["id"]

    res = teacher_client.post(
        f"/courses/{course_id}/videos",
        json={
            "title": "Intro to Web",
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "chunks": [
                {"start": 10, "end": 15, "title": "Hook"},
                {"start": "1:00", "end": "1:05", "title": "Chorus"}
            ]
        }
    )
    assert res.status_code == 201
    v_data = res.json()
    assert len(v_data["chunks"]) == 2
    assert v_data["chunks"][0]["start"] == 10.0
    assert v_data["chunks"][0]["end"] == 15.0
    assert v_data["chunks"][1]["start"] == 60.0
    assert v_data["chunks"][1]["end"] == 65.0
    assert v_data["chunks"][1]["startFormatted"] == "01:00"


