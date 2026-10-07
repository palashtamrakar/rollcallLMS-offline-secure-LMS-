from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from fastapi.staticfiles import StaticFiles

from .db import BASE_DIR, PRESENTATIONS_DIR, UPLOAD_DIR, init_db
from .routers import auth, courses, enrollment, presentations, quizzes, results, videos



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Roll Call LMS API",
    description="REST API for Roll Call two-persona Learning Ledger",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware to allow seamless frontend connection from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
routers = [
    auth.router,
    courses.router,
    videos.router,
    presentations.router,
    quizzes.router,
    enrollment.router,
    results.router,
]

for r in routers:
    app.include_router(r)
    app.include_router(r, prefix="/api")

# Mount static media, presentations, and assets directories for streaming and direct access
app.mount("/media/presentations", StaticFiles(directory=str(PRESENTATIONS_DIR)), name="media_presentations")
app.mount("/api/media/presentations", StaticFiles(directory=str(PRESENTATIONS_DIR)), name="api_media_presentations")

app.mount("/media", StaticFiles(directory=str(UPLOAD_DIR)), name="media")
app.mount("/api/media", StaticFiles(directory=str(UPLOAD_DIR)), name="api_media")

ASSETS_DIR = BASE_DIR / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
    app.mount("/api/assets", StaticFiles(directory=str(ASSETS_DIR)), name="api_assets")




@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "roll-call-lms"}


# Serve index.html if requested at root or if frontend static assets exist
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
INDEX_HTML_PATH = ROOT_DIR / "index.html"


@app.get("/", include_in_schema=False)
def serve_root():
    if INDEX_HTML_PATH.exists():
        return FileResponse(INDEX_HTML_PATH)
    return JSONResponse({"message": "Roll Call API is running. Visit /docs for Swagger documentation."})
