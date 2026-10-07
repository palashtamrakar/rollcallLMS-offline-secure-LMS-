---
name: roll-call-backend
description: Use this skill when building, extending, or reviewing the Python backend for "Roll Call", a two-persona (teacher/student) learning management app. Covers the data model, REST API contract, grading logic, and how it maps onto the existing frontend (roll-call-lms.html) so the two can be wired together with minimal frontend changes. Trigger whenever the user asks for a backend, API, database, or server for Roll Call / this LMS, or asks to replace its in-browser storage with a real service.
license: Complete terms in LICENSE.txt
---

# Roll Call — Backend Skill

## What you're building

A REST API that backs the existing single-file frontend (`roll-call-lms.html`). That frontend currently persists everything through a browser-only `window.storage` key-value API (one shared JSON blob at key `lms-db`, plus a personal `identity` key). Your job is to replace that with a real Python backend and a real database, while keeping the **data shapes** close enough that the frontend only needs its storage calls swapped for `fetch()` calls — not a rewrite.

Read this whole file before writing code. It defines the domain model, the exact endpoints expected, grading behavior, and known edge cases from the original implementation.

## Recommended stack

Unless the user specifies otherwise, use:
- **FastAPI** for the API layer (async, automatic OpenAPI docs, Pydantic validation)
- **SQLModel** (or SQLAlchemy + Pydantic if the user prefers) for the ORM
- **SQLite** for local/dev persistence (a single `roll_call.db` file); mention Postgres as the drop-in upgrade for production
- **Uvicorn** as the ASGI server
- **passlib / python-jose** only if you're adding real authentication (see "Auth" below — the original frontend has none, so don't over-build unless asked)

Project layout:
```
backend/
  app/
    __init__.py
    main.py          # FastAPI app, CORS, router includes
    models.py        # SQLModel table models
    schemas.py        # Pydantic request/response schemas
    db.py             # engine, session dependency
    routers/
      auth.py
      courses.py
      enrollment.py
      quizzes.py
      results.py
    grading.py         # scoring logic, isolated for testability
  tests/
    test_courses.py
    test_quizzes.py
    ...
  requirements.txt
  README.md
```

## Domain model

Mirror these entities. Field names are chosen to match the frontend's JS objects one-to-one wherever possible, to minimize glue code.

### User
- `id: str` (primary key — the frontend generates client-side ids like `teacher-x7k2p9q`; either accept client-supplied ids at signup or switch to server-generated UUIDs and update the frontend to store whatever id the server returns)
- `name: str`
- `role: Literal["teacher","student"]`

There is **no password in the original app** — "login" is just picking a name and a role. If the user asks for this to stay a low-stakes prototype, keep it that simple (see Auth section). If they ask for real accounts, add a password/OAuth flow but keep the `role` field and the rest of the model unchanged.

### Course
- `id: str`
- `title: str`
- `description: str`
- `teacher_id: str` (FK → User)
- `videos: [Video]`
- `quizzes: [Quiz]`
- enrollment is tracked via the `Enrollment` table below, not inline arrays (the frontend uses inline `enrolled: [studentId]` / `pending: [studentId]` arrays — translate these to rows with a `status` column)

### Video
- `id: str`
- `course_id: str` (FK)
- `title: str`
- `youtube_id: str` — **not** the raw URL. Extract the 11-character video id server-side (see "YouTube ID extraction" below) so the frontend can keep doing `https://www.youtube.com/embed/{youtube_id}` unchanged.

### Quiz
- `id: str`
- `course_id: str` (FK)
- `title: str`
- `questions: [Question]`

### Question
- `id: str`
- `quiz_id: str` (FK)
- `text: str`
- `options: [str]` (the original UI always builds exactly 4 options per question, but don't hard-code that assumption — validate "at least 2" so the model stays reusable)
- `correct_index: int` — **never serialize this field to students.** It must be present in teacher-facing responses and completely absent from any response a student sees before submitting the quiz (see "Grading" below).

### Enrollment
- `id`, `course_id` (FK), `student_id` (FK)
- `status: Literal["pending","enrolled"]`
- Composite unique constraint on `(course_id, student_id)` — a student can only have one enrollment row per course. Requesting again while pending is a no-op; requesting again after being declined (i.e. no row) creates a new pending row.

### QuizAttempt (called "results" in the frontend)
- `id`, `student_id` (FK), `course_id` (FK), `quiz_id` (FK)
- `score: int`, `total: int`, `percent: int` (rounded, `round(score/total*100)`)
- `answers: JSON` — map of `question_id -> selected_option_index`, stored so a student can review a past attempt
- `submitted_at: datetime`
- Multiple attempts per student per quiz are allowed and all are kept (this is how the "trend over time" sparkline in the teacher and student views works) — do not overwrite or dedupe.

## API contract

All endpoints return JSON. Use standard status codes: `201` on create, `200` on read/update, `204` on delete, `403` when a role does the wrong thing (e.g. a student hitting a teacher-only route), `404` when a referenced course/quiz/student doesn't exist, `409` for the duplicate-enrollment-request case.

Every route that mutates course content must check `course.teacher_id == current_user.id` (or just `current_user.role == "teacher"` if you're not scoping courses per-teacher — check with the user which behavior they want; the frontend currently shows **all** courses to **every** teacher, so the default is: any teacher can edit any course, unless told otherwise).

### Auth / identity
```
POST /auth/login          body: {name: str, role: "teacher"|"student"}
                           -> 200 {id, name, role}
                           Creates the user on first login, matched by (name, role) unless the
                           user asks for something stricter. Returns the same id on subsequent
                           logins with the same name+role so a student's history is continuous.
```
Return the `id` to the frontend so it can store it exactly where it currently stores the `identity` object (swap `window.storage.set('identity', ...)` for storing this response, e.g. in `localStorage` or an httpOnly cookie the server sets).

### Courses
```
GET    /courses                          -> list all courses (summary: id, title, description,
                                             video_count, quiz_count, enrolled_count, pending_count)
                                             — used for the student "browse" tab and teacher "courses" tab
GET    /courses/{course_id}               -> full course detail including videos and quizzes
                                             (omit correct_index from questions unless requester is
                                             the teacher — see Grading)
POST   /courses            [teacher only] body: {title, description} -> 201 course
DELETE /courses/{course_id} [teacher only] -> 204, cascades to videos/quizzes/enrollments/attempts
```

### Videos
```
POST   /courses/{course_id}/videos   [teacher only]
       body: {title: str, youtube_url: str}
       -> extract youtube_id server-side (see helper below); 400 if it can't be parsed
DELETE /courses/{course_id}/videos/{video_id}   [teacher only]
```

### Quizzes
```
POST   /courses/{course_id}/quizzes   [teacher only]
       body: {title: str, questions: [{text, options: [str], correct_index: int}]}
       -> validate: >=1 question, every question has >=2 options,
          0 <= correct_index < len(options) for every question
DELETE /courses/{course_id}/quizzes/{quiz_id}   [teacher only]
```

### Enrollment
```
POST   /courses/{course_id}/enrollment-requests   [student only]
       -> creates a "pending" row for current student; 409 if already pending or enrolled
POST   /courses/{course_id}/enrollment-requests/{student_id}/approve   [teacher only]
       -> flips status to "enrolled"
POST   /courses/{course_id}/enrollment-requests/{student_id}/decline   [teacher only]
       -> deletes the pending row
DELETE /courses/{course_id}/students/{student_id}   [teacher only]
       -> removes an enrolled student
GET    /courses/{course_id}/roster   [teacher only]
       -> {pending: [User], enrolled: [User]}
```

### Taking quizzes / grading
```
POST   /quizzes/{quiz_id}/attempts   [student, must be enrolled in the parent course]
       body: {answers: {question_id: option_index, ...}}
       -> server grades: for each question, answers.get(q.id) == q.correct_index
          -> score, total, percent = round(score/total*100)
          -> 400 if any question is missing from `answers`
          -> store the attempt; return {score, total, percent, id, submitted_at}
          NEVER trust a client-submitted score. Grading must happen server-side against
          the stored correct_index, exactly like the original frontend does client-side today —
          the difference is this is now the trust boundary, so don't skip it.
```

### Results
```
GET /students/{student_id}/results                    -> that student's own attempts, all courses
                                                           (self, or teacher of the relevant course)
GET /courses/{course_id}/results                       [teacher only]
       -> per enrolled student: attempts list + computed avg_percent, last_percent
       (the frontend renders this into a sparkline client-side from the raw attempt list —
        just return the ordered list of {quiz_id, quiz_title, score, total, percent, submitted_at}
        per student; don't pre-render the chart)
```

## YouTube ID extraction (server-side, replaces the JS version)

Port this logic so the backend is the single source of truth once you remove client trust:
```python
import re

YOUTUBE_PATTERNS = [
    r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    r"[?&]v=([a-zA-Z0-9_-]{11})",
]

def extract_youtube_id(raw: str) -> str | None:
    raw = raw.strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", raw):
        return raw
    for pattern in YOUTUBE_PATTERNS:
        m = re.search(pattern, raw)
        if m:
            return m.group(1)
    return None
```
Return `400` with a clear message (`"Couldn't read a YouTube video id from that URL"`) if this returns `None` — don't silently store a bad value.

## Auth: how far to go

The original frontend has **no password and no session security** — "logging in" is naming yourself. Default to matching that unless the user asks for more:
- **Minimal (default, matches current app):** `/auth/login` returns a user id; the frontend stores it and sends it back as a header (e.g. `X-User-Id`) on every request. No passwords. Good for demos, internal tools, classrooms where trust is already established out of band. Say this out loud to the user so they know the tradeoff.
- **If asked for real auth:** add password hashing (`passlib[bcrypt]`) or OAuth, issue a JWT or session cookie from `/auth/login`, and require it via a FastAPI dependency (`Depends(get_current_user)`) on every non-public route. Keep the `role` field either way — it's core to the app's two-persona design, not an auth add-on.

Either way, **never** let the client assert its own role on a mutating request — role must come from the looked-up user record server-side, not from a request body field, or a student could POST a course by claiming `role: "teacher"`.

## Wiring the existing frontend to this API

`roll-call-lms.html` currently does everything through these calls — replace each with a `fetch`:

| Frontend call | Replace with |
|---|---|
| `window.storage.get('identity', false)` | read whatever you stored after `/auth/login` (e.g. `localStorage.getItem('rollcall_user')`) |
| `window.storage.set('identity', ...)` | after `POST /auth/login`, store the returned user |
| `window.storage.get('lms-db', true)` | `GET /courses` (list) + per-course `GET /courses/{id}` as needed, since a single monolithic blob no longer makes sense with a real DB |
| `window.storage.set('lms-db', ...)` | replaced entirely by the specific POST/DELETE endpoints above — there is no more "save the whole db" step |
| every mutation in `bindTeacherEvents` / `bindStudentEvents` (`data-create-course`, `data-add-video`, `data-approve`, `data-submit-quiz`, etc.) | the matching endpoint from the table above, called directly instead of mutating `state.db` locally |

Practical migration order: get `/auth/login`, `GET /courses`, and `POST /courses` working first and confirm the "Courses & Content" tab renders from real API data before touching enrollment and quizzes — the app degrades gracefully tab-by-tab since each tab fetches independently.

## Things the original frontend already decided — keep these unless told otherwise

- Any teacher can manage any course (no per-teacher ownership restriction in the UI)
- Students can hold multiple quiz attempts per quiz; nothing is ever overwritten
- Declining a pending request just removes it — a declined student can request again later
- A course delete cascades to its videos, quizzes, enrollments, and attempts
- Percent scores are rounded to the nearest whole number, not truncated

## Testing

At minimum, cover with pytest + `TestClient`:
- Grading correctness (right/wrong/partial answers → correct score and percent)
- A student cannot submit an attempt for a course they aren't enrolled in
- A student cannot see `correct_index` before submitting
- Duplicate enrollment requests are rejected (409), re-requesting after decline works
- YouTube id extraction against each URL shape (`youtu.be/...`, `watch?v=...`, `embed/...`, shorts, bare id, garbage input)
- Role enforcement: a student hitting a teacher-only route gets 403

## Non-goals

Don't add features the frontend doesn't have a surface for yet (file uploads, email notifications, grading rubrics beyond MCQ, etc.) unless the user asks — build the backend this frontend needs, not a bigger platform.