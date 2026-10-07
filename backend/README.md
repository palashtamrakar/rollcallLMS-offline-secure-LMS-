# Roll Call LMS — Backend

A production-ready Python REST API backing the **Roll Call** two-persona Learning Ledger app, built with **FastAPI**, **SQLModel**, and **SQLite** according to the specifications in `skill/backend.md`.

## Features
- **Self-Contained & 100% Offline Ready**: Operates completely on localhost with zero external dependencies, fonts, or CDNs required.
- **Local Video Upload & Streaming**: Teachers can upload video files (MP4, WebM, MOV, MKV, OGG) stored directly on the server with native HTML5 seekable streaming (HTTP 206 Partial Content / Range requests).
- **PowerPoint & Slide Deck Integration**: Teachers can upload PowerPoint presentations (`.pptx`, `.ppt`) which are automatically parsed for slide content, bullet points, speaker notes, diagrams, tables, and images. Also supports online presentation decks (Google Slides, OneDrive / PowerPoint Online, Canva).
- **Interactive PPT Slide Viewer**: Slide-by-slide navigation, slide stepper chips, fullscreen presentation mode, collapsible speaker notes drawer, and direct PPTX download.
- **YouTube & Online Video Support**: Teachers can also optionally link YouTube videos when internet is available.
- **Two-Persona Identity System**: Support for Teachers and Students with automatic persistence and role protection.
- **Course & Content Management**: Full CRUD for courses, video integration, PPT presentations, and multi-question quiz builder.
- **Roster & Enrollment Workflow**: Students request to join; teachers approve, decline, or remove students.
- **Server-Side Grading & Security**: Client-submitted answers are graded server-side against stored answer keys. Answer keys are concealed from student queries.
- **Attempt History & Trend Sparklines**: Multi-attempt persistence per student with average and last attempt metrics.
- **FastAPI OpenAPI Docs**: Interactive Swagger documentation available at `/docs` and ReDoc at `/redoc`.

---

## Setup & Running

### 1. Activate Environment & Install Dependencies
```bash
# Using the pre-configured virtual environment:
./backend/.venv/bin/pip install -r backend/requirements.txt
```

### 2. Run the Development Server
```bash
./backend/.venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

Once running:
- Open `http://localhost:8000` to interact with the LMS frontend.
- Open `http://localhost:8000/docs` to view the interactive Swagger API documentation.

---

## Running Tests

Run the complete test suite with `pytest`:

```bash
./backend/.venv/bin/pytest backend/tests -v
```

---

## API Summary

| Method | Path | Description | Access |
|---|---|---|---|
| `POST` | `/auth/login` | Login or create user by name + role | Public |
| `GET` | `/auth/me` | Get current user profile | Auth (`X-User-Id`) |
| `GET` | `/courses` | List all courses (redacts correct_index for students) | Public / Auth |
| `GET` | `/courses/{id}` | Full course detail with videos, presentations, and quizzes | Public / Auth |
| `POST` | `/courses` | Create a new course | Teacher |
| `DELETE` | `/courses/{id}` | Delete a course (cascades to child records and local files) | Teacher |
| `POST` | `/courses/{id}/videos/upload` | Upload local video file (MP4, WebM, MOV, etc.) | Teacher |
| `POST` | `/courses/{id}/videos` | Add YouTube video (auto-extracts 11-char YouTube ID) | Teacher |
| `GET` | `/videos/{vid}/stream` | Stream local video file with HTTP Range support | Public / Browser |
| `DELETE` | `/courses/{id}/videos/{vid}` | Remove video and delete local file from disk | Teacher |
| `POST` | `/courses/{id}/presentations/upload` | Upload PowerPoint (.pptx/.ppt) with automated slide parsing | Teacher |
| `POST` | `/courses/{id}/presentations` | Add online slide link (Google Slides, OneDrive, Canva) | Teacher |
| `GET` | `/presentations/{pid}/download` | Download raw PowerPoint presentation file | Public / Browser |
| `GET` | `/presentations/{pid}/slides` | Get structured slide data (titles, bullets, tables, notes, images) | Public / Auth |
| `DELETE` | `/courses/{id}/presentations/{pid}` | Remove presentation and clean up disk files/images | Teacher |
| `POST` | `/courses/{id}/quizzes` | Create a quiz with multiple questions | Teacher |
| `DELETE` | `/courses/{id}/quizzes/{qid}` | Delete a quiz | Teacher |
| `POST` | `/courses/{id}/enrollment-requests` | Request course enrollment | Student |
| `POST` | `/courses/{id}/enrollment-requests/{sid}/approve` | Approve student enrollment | Teacher |
| `POST` | `/courses/{id}/enrollment-requests/{sid}/decline` | Decline student enrollment | Teacher |
| `DELETE` | `/courses/{id}/students/{sid}` | Remove enrolled student | Teacher |
| `GET` | `/courses/{id}/roster` | View pending and enrolled students | Teacher |
| `POST` | `/quizzes/{id}/attempts` | Submit answers and receive server-graded score | Enrolled Student |
| `GET` | `/students/{id}/results` | View student's attempts history | Self or Teacher |
| `GET` | `/courses/{id}/results` | View student scorecard & sparkline data | Teacher |

