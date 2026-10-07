import json
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from ..db import UPLOAD_DIR, get_session
from ..dependencies import require_teacher
from ..models import Course, User, Video, generate_id
from ..schemas import (
    VideoChunk,
    VideoCreateRequest,
    VideoResponse,
    format_seconds_to_timestamp,
    parse_time_to_seconds,
)
from ..youtube import extract_youtube_id

router = APIRouter(tags=["Videos"])

ALLOWED_VIDEO_EXTS = {
    ".mp4",
    ".webm",
    ".ogg",
    ".ogv",
    ".mov",
    ".mkv",
    ".avi",
    ".m4v",
    ".wmv",
    ".flv",
}


def build_video_response(video: Video) -> VideoResponse:

    """Build response model for a Video object with calculated streaming URL and chunks."""
    stream_url = (
        f"/api/videos/{video.id}/stream"
        if video.video_type == "local"
        else (f"https://www.youtube.com/watch?v={video.youtube_id}" if video.youtube_id else "")
    )
    chunk_objs: list[VideoChunk] = []
    for c in video.chunks:
        if isinstance(c, dict):
            s = parse_time_to_seconds(c.get("start", 0))
            e = parse_time_to_seconds(c.get("end", 0))
            title = str(c.get("title", "") or c.get("label", "")).strip()
            chunk_objs.append(
                VideoChunk(
                    start=s,
                    end=e,
                    title=title,
                )
            )
    return VideoResponse(
        id=video.id,
        course_id=video.course_id,
        title=video.title,
        video_type=video.video_type or "youtube",
        youtube_id=video.youtube_id,
        file_name=video.file_name,
        file_path=video.file_path,
        content_type=video.content_type,
        file_size=video.file_size,
        url=stream_url,
        chunks=chunk_objs,
    )


@router.post("/courses/{course_id}/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def add_video(
    course_id: str,
    data: VideoCreateRequest,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> VideoResponse:
    """Add a YouTube video to a course with optional playback chunks (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    youtube_id = extract_youtube_id(data.youtube_url)
    if not youtube_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Couldn't read a YouTube video id from that URL",
        )

    clean_chunks = []
    for c in data.chunks or []:
        s = parse_time_to_seconds(c.start)
        e = parse_time_to_seconds(c.end)
        if e > s:
            clean_chunks.append({
                "start": s,
                "end": e,
                "title": c.title or "",
                "start_formatted": format_seconds_to_timestamp(s),
                "end_formatted": format_seconds_to_timestamp(e),
            })

    video = Video(
        id=generate_id("vid"),
        course_id=course_id,
        title=data.title,
        video_type="youtube",
        youtube_id=youtube_id,
        chunks_json=json.dumps(clean_chunks),
    )
    session.add(video)
    session.commit()
    session.refresh(video)
    return build_video_response(video)


@router.post("/courses/{course_id}/videos/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_local_video(
    course_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    chunks: Optional[str] = Form(None),
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> VideoResponse:
    """Upload a local video file with optional chunk/segment configuration (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No video file provided")

    raw_ext = Path(file.filename).suffix.lower()
    is_video_mime = bool(file.content_type and file.content_type.startswith("video/"))
    if raw_ext not in ALLOWED_VIDEO_EXTS and not is_video_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{raw_ext}'. Please upload a video file (.mp4, .webm, .mov, etc.)",
        )

    vid_id = generate_id("vid")
    ext = raw_ext if raw_ext in ALLOWED_VIDEO_EXTS else ".mp4"
    stored_filename = f"{vid_id}{ext}"
    dest_path = UPLOAD_DIR / stored_filename

    # Save to uploads directory
    file_size = 0
    with open(dest_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)
            file_size += len(chunk)

    if file_size == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    clean_title = (
        title.strip()
        if (title and title.strip())
        else Path(file.filename).stem.replace("_", " ").replace("-", " ").strip()
    )
    if not clean_title:
        clean_title = "Untitled Video"

    content_type = file.content_type
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(dest_path.name)
        content_type = guessed_type or "video/mp4"

    # Parse and validate chunks if provided
    parsed_chunks: list[dict] = []
    if chunks:
        try:
            raw_list = json.loads(chunks) if isinstance(chunks, str) else chunks
            if isinstance(raw_list, list):
                for item in raw_list:
                    if isinstance(item, dict):
                        s = parse_time_to_seconds(item.get("start", 0))
                        e = parse_time_to_seconds(item.get("end", 0))
                        lbl = str(item.get("title", "") or item.get("label", "")).strip()
                        if e > s:
                            parsed_chunks.append({
                                "start": s,
                                "end": e,
                                "title": lbl,
                                "start_formatted": format_seconds_to_timestamp(s),
                                "end_formatted": format_seconds_to_timestamp(e),
                            })
        except Exception:
            pass

    video = Video(
        id=vid_id,
        course_id=course_id,
        title=clean_title,
        video_type="local",
        youtube_id=None,
        file_name=stored_filename,
        file_path=str(dest_path),
        content_type=content_type,
        file_size=file_size,
        chunks_json=json.dumps(parsed_chunks),
    )
    session.add(video)
    session.commit()
    session.refresh(video)
    return build_video_response(video)



@router.get("/videos/{video_id}/stream")
def stream_video(
    video_id: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Stream a local video file with HTTP Range partial content support for seekable playback."""
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    if video.video_type != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This video is an external link (YouTube), not a local video file",
        )

    file_path = Path(video.file_path) if video.file_path else (UPLOAD_DIR / (video.file_name or ""))
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type=video.content_type or "video/mp4",
        filename=video.file_name or f"{video.id}.mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.delete("/courses/{course_id}/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_video(
    course_id: str,
    video_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> Response:
    """Remove a video from a course and delete local video file if applicable (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    video = session.get(Video, video_id)
    if not video or video.course_id != course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found in this course")

    # Clean up local file from disk if local video
    if video.video_type == "local":
        if video.file_path:
            p = Path(video.file_path)
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)
        if video.file_name:
            p = UPLOAD_DIR / video.file_name
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)

    session.delete(video)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

