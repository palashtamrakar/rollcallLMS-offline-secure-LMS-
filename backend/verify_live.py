import httpx

BASE = "http://127.0.0.1:8000"


def main():
    print("1. Health Check...")
    r = httpx.get(f"{BASE}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print("   ✓ Health:", r.json())

    print("2. Teacher Login...")
    r = httpx.post(f"{BASE}/auth/login", json={"name": "Prof. Higgins", "role": "teacher"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    teacher = r.json()
    teacher_id = teacher["id"]
    teacher_headers = {"X-User-Id": teacher_id}
    print("   ✓ Teacher ID:", teacher_id)

    print("3. Teacher Creates Course...")
    r = httpx.post(
        f"{BASE}/courses",
        json={"title": "Introduction to Computer Science", "description": "Foundations of programming and algorithms"},
        headers=teacher_headers,
    )
    assert r.status_code == 201, f"Course creation failed: {r.text}"
    course = r.json()
    course_id = course["id"]
    print("   ✓ Course ID:", course_id)

    print("4. Teacher Adds YouTube Video...")
    r = httpx.post(
        f"{BASE}/courses/{course_id}/videos",
        json={"title": "Intro to Computing", "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        headers=teacher_headers,
    )
    assert r.status_code == 201, f"Video creation failed: {r.text}"
    video = r.json()
    yid = video.get("youtube_id") or video.get("youtubeId")
    print("   ✓ YouTube Video added with ID:", yid)

    print("4b. Teacher Uploads Local Video File with Chunks...")
    fake_video_bytes = b"\x00\x00\x00\x18ftypmp42" + b"Local video test data" * 100
    chunks_json_str = '[{"start": "00:30", "end": "00:32", "title": "Intro"}, {"start": "0:55", "end": "0:59", "title": "Summary"}]'
    r = httpx.post(
        f"{BASE}/courses/{course_id}/videos/upload",
        files={"file": ("lecture_binary_logic.mp4", fake_video_bytes, "video/mp4")},
        data={"title": "Lecture 2: Binary Logic", "chunks": chunks_json_str},
        headers=teacher_headers,
    )
    assert r.status_code == 201, f"Local video upload failed: {r.text}"
    local_vid = r.json()
    local_vid_id = local_vid["id"]
    assert len(local_vid["chunks"]) == 2
    assert local_vid["chunks"][0]["start"] == 30.0
    assert local_vid["chunks"][0]["end"] == 32.0
    print("   ✓ Local Video uploaded with ID:", local_vid_id, "Title:", local_vid["title"], "Chunks:", len(local_vid["chunks"]))

    print("4c. Stream Local Video...")
    r = httpx.get(f"{BASE}/videos/{local_vid_id}/stream")
    assert r.status_code == 200, f"Video streaming failed: {r.text}"
    assert r.content == fake_video_bytes
    print("   ✓ Local Video streamed successfully (bytes verified)")



    print("5. Teacher Adds Quiz...")
    r = httpx.post(
        f"{BASE}/courses/{course_id}/quizzes",
        json={
            "title": "Quiz 1: Fundamentals",
            "questions": [
                {
                    "text": "What is the binary representation of decimal 5?",
                    "options": ["100", "101", "110", "111"],
                    "correct_index": 1,
                }
            ],
        },
        headers=teacher_headers,
    )
    assert r.status_code == 201, f"Quiz creation failed: {r.text}"
    quiz = r.json()
    quiz_id = quiz["id"]
    q_id = quiz["questions"][0]["id"]
    print("   ✓ Quiz created with ID:", quiz_id)

    print("6. Student Login...")
    r = httpx.post(f"{BASE}/auth/login", json={"name": "Ada Lovelace", "role": "student"})
    assert r.status_code == 200, f"Student login failed: {r.text}"
    student = r.json()
    student_id = student["id"]
    student_headers = {"X-User-Id": student_id}
    print("   ✓ Student ID:", student_id)

    print("7. Student Requests Enrollment...")
    r = httpx.post(f"{BASE}/courses/{course_id}/enrollment-requests", headers=student_headers)
    assert r.status_code == 201, f"Enrollment request failed: {r.text}"
    print("   ✓ Enrollment request submitted (status: pending)")

    print("8. Teacher Reviews Roster & Approves...")
    r = httpx.get(f"{BASE}/courses/{course_id}/roster", headers=teacher_headers)
    roster = r.json()
    assert len(roster["pending"]) == 1
    r = httpx.post(f"{BASE}/courses/{course_id}/enrollment-requests/{student_id}/approve", headers=teacher_headers)
    assert r.status_code == 200, f"Approval failed: {r.text}"
    print("   ✓ Teacher approved enrollment")

    print("9. Student Takes Quiz & Submits Server-Graded Answers...")
    r = httpx.post(f"{BASE}/quizzes/{quiz_id}/attempts", json={"answers": {q_id: 1}}, headers=student_headers)
    assert r.status_code == 201, f"Quiz attempt submission failed: {r.text}"
    attempt = r.json()
    print(f"   ✓ Server graded attempt: Score {attempt['score']}/{attempt['total']} ({attempt['percent']}%)")
    assert attempt["percent"] == 100

    print("10. Student Views Their Results...")
    r = httpx.get(f"{BASE}/students/{student_id}/results", headers=student_headers)
    assert r.status_code == 200
    results = r.json()
    print(f"   ✓ Student has {len(results)} attempt(s) in ledger")

    print("11. Teacher Views Course Results Ledger...")
    r = httpx.get(f"{BASE}/courses/{course_id}/results", headers=teacher_headers)
    assert r.status_code == 200
    c_results = r.json()
    avg_pct = c_results[0].get("avg_percent") or c_results[0].get("avgPercent")
    print(f"   ✓ Teacher course ledger has {len(c_results)} enrolled student(s), avg score: {avg_pct}%")

    print("\n*** ALL LIVE END-TO-END VERIFICATIONS PASSED 100%! ***")


if __name__ == "__main__":
    main()
