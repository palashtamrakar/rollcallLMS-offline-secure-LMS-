import json
import mimetypes
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from ..db import PRESENTATIONS_DIR, get_session
from ..dependencies import require_teacher
from ..models import Course, Presentation, User, generate_id
from ..pptx_parser import normalize_slide_embed_url, parse_pptx_file
from ..schemas import (
    PresentationCreateRequest,
    PresentationResponse,
    SlideData,
    SlideImage,
    SlideMappingUpdateRequest,
    SlideTable,
    SlideTextBlock,
)

router = APIRouter(tags=["Presentations"])

ALLOWED_PPT_EXTS = {".pptx", ".ppt"}


def build_presentation_response(presentation: Presentation) -> PresentationResponse:
    """Build response model for a Presentation with calculated download URL and structured slides."""
    download_url = (
        f"/api/presentations/{presentation.id}/download"
        if presentation.presentation_type == "local"
        else None
    )

    slide_objs: List[SlideData] = []
    for s in presentation.slides:
        if isinstance(s, dict):
            text_blocks = [
                SlideTextBlock(
                    text=tb.get("text", ""),
                    level=tb.get("level", 0),
                    is_bold=tb.get("is_bold", False),
                    is_title=tb.get("is_title", False),
                )
                for tb in s.get("text_blocks", [])
                if isinstance(tb, dict)
            ]
            tables = [
                SlideTable(
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                )
                for t in s.get("tables", [])
                if isinstance(t, dict)
            ]
            images = [
                SlideImage(
                    url=img.get("url", ""),
                    filename=img.get("filename", ""),
                    content_type=img.get("content_type"),
                )
                for img in s.get("images", [])
                if isinstance(img, dict)
            ]
            slide_objs.append(
                SlideData(
                    index=s.get("index", len(slide_objs) + 1),
                    title=s.get("title", ""),
                    notes=s.get("notes"),
                    video_id=s.get("video_id") or s.get("videoId"),
                    video_start=s.get("video_start") or s.get("videoStart"),
                    video_end=s.get("video_end") or s.get("videoEnd"),
                    text_blocks=text_blocks,
                    tables=tables,
                    images=images,
                )
            )

    return PresentationResponse(
        id=presentation.id,
        course_id=presentation.course_id,
        title=presentation.title,
        description=presentation.description or "",
        presentation_type=presentation.presentation_type or "local",
        embed_url=presentation.embed_url,
        file_name=presentation.file_name,
        file_size=presentation.file_size,
        slide_count=presentation.slide_count or len(slide_objs),
        download_url=download_url,
        slides=slide_objs,
    )


@router.post(
    "/courses/{course_id}/presentations/upload",
    response_model=PresentationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_presentation(
    course_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(""),
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> PresentationResponse:
    """Upload a PowerPoint presentation (.pptx) to a course with automated slide, notes, and image extraction (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No presentation file provided")

    raw_ext = Path(file.filename).suffix.lower()
    is_ppt_mime = bool(
        file.content_type
        and (
            "presentation" in file.content_type
            or "powerpoint" in file.content_type
            or "office" in file.content_type
        )
    )

    if raw_ext not in ALLOWED_PPT_EXTS and not is_ppt_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{raw_ext}'. Please upload a PowerPoint presentation (.pptx or .ppt)",
        )

    pres_id = generate_id("pres")
    ext = raw_ext if raw_ext in ALLOWED_PPT_EXTS else ".pptx"
    stored_filename = f"{pres_id}{ext}"
    dest_path = PRESENTATIONS_DIR / stored_filename

    # Save presentation file to uploads directory
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
        clean_title = "Untitled Presentation"

    content_type = file.content_type
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(dest_path.name)
        content_type = guessed_type or "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    # Parse PPTX slides
    slides_list: list[dict] = []
    slide_count = 0
    if ext == ".pptx":
        try:
            parsed_data = parse_pptx_file(
                file_path=dest_path,
                pres_id=pres_id,
                images_base_dir=PRESENTATIONS_DIR,
                media_url_prefix="/media/presentations",
            )
            slides_list = parsed_data.get("slides", [])
            slide_count = parsed_data.get("slide_count", len(slides_list))
        except Exception as err:
            # If parsing failed but file is saved, create a fallback single slide
            slides_list = [
                {
                    "index": 1,
                    "title": clean_title,
                    "notes": f"PowerPoint presentation ready for download. ({err})",
                    "text_blocks": [
                        {"text": "Uploaded Presentation File", "level": 0, "is_bold": True, "is_title": True},
                        {"text": f"File name: {file.filename}", "level": 0, "is_bold": False, "is_title": False},
                        {"text": "Click 'Download PPTX' below to view full slides in PowerPoint.", "level": 0, "is_bold": False, "is_title": False},
                    ],
                    "tables": [],
                    "images": [],
                }
            ]
            slide_count = 1
    else:
        # For legacy .ppt
        slides_list = [
            {
                "index": 1,
                "title": clean_title,
                "notes": "Legacy .ppt file uploaded. Download to view in PowerPoint.",
                "text_blocks": [
                    {"text": "Legacy PowerPoint Presentation (.ppt)", "level": 0, "is_bold": True, "is_title": True},
                    {"text": f"File name: {file.filename}", "level": 0, "is_bold": False, "is_title": False},
                    {"text": "Download the file below to open in Microsoft PowerPoint.", "level": 0, "is_bold": False, "is_title": False},
                ],
                "tables": [],
                "images": [],
            }
        ]
        slide_count = 1

    presentation = Presentation(
        id=pres_id,
        course_id=course_id,
        title=clean_title,
        description=description.strip() if description else "",
        presentation_type="local",
        embed_url=None,
        file_name=stored_filename,
        file_path=str(dest_path),
        content_type=content_type,
        file_size=file_size,
        slide_count=slide_count,
        slides_json=json.dumps(slides_list),
    )
    session.add(presentation)
    session.commit()
    session.refresh(presentation)
    return build_presentation_response(presentation)


@router.post(
    "/courses/{course_id}/presentations",
    response_model=PresentationResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_embed_presentation(
    course_id: str,
    data: PresentationCreateRequest,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> PresentationResponse:
    """Add an online/embed presentation link (Google Slides, OneDrive, Canva, etc.) to a course (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    normalized_url = normalize_slide_embed_url(data.embed_url)
    if not normalized_url or not normalized_url.startswith("http"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid presentation URL provided. Must start with http:// or https://",
        )

    presentation = Presentation(
        id=generate_id("pres"),
        course_id=course_id,
        title=data.title,
        description=data.description or "",
        presentation_type="embed",
        embed_url=normalized_url,
        file_path=None,
        file_name=None,
        content_type=None,
        file_size=None,
        slide_count=1,
        slides_json="[]",
    )
    session.add(presentation)
    session.commit()
    session.refresh(presentation)
    return build_presentation_response(presentation)


@router.get("/presentations/{presentation_id}/download")
def download_presentation(
    presentation_id: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    """Download a local PowerPoint presentation file."""
    presentation = session.get(Presentation, presentation_id)
    if not presentation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presentation not found")

    if presentation.presentation_type != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This presentation is an external embed link, not a local file",
        )

    file_path = (
        Path(presentation.file_path)
        if presentation.file_path
        else (PRESENTATIONS_DIR / (presentation.file_name or ""))
    )
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presentation file not found on disk")

    download_filename = presentation.file_name or f"{presentation.title.replace(' ', '_')}.pptx"
    return FileResponse(
        path=str(file_path),
        media_type=presentation.content_type or "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=download_filename,
    )


@router.get("/presentations/{presentation_id}/slides", response_model=List[SlideData])
def get_presentation_slides(
    presentation_id: str,
    session: Session = Depends(get_session),
) -> List[SlideData]:
    """Get structured slide contents for a presentation."""
    presentation = session.get(Presentation, presentation_id)
    if not presentation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presentation not found")

    resp = build_presentation_response(presentation)
    return resp.slides


@router.delete(
    "/courses/{course_id}/presentations/{presentation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_presentation(
    course_id: str,
    presentation_id: str,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> Response:
    """Remove a presentation from a course and delete local file & extracted images from disk (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    presentation = session.get(Presentation, presentation_id)
    if not presentation or presentation.course_id != course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presentation not found in this course")

    # Clean up local presentation file and extracted image directory
    if presentation.presentation_type == "local":
        if presentation.file_path:
            p = Path(presentation.file_path)
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)
        if presentation.file_name:
            p = PRESENTATIONS_DIR / presentation.file_name
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)

        pres_folder = PRESENTATIONS_DIR / presentation.id
        if pres_folder.exists() and pres_folder.is_dir():
            shutil.rmtree(pres_folder, ignore_errors=True)

    session.delete(presentation)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/courses/{course_id}/presentations/{presentation_id}/slide-mappings",
    response_model=PresentationResponse,
)
def update_slide_mappings(
    course_id: str,
    presentation_id: str,
    data: SlideMappingUpdateRequest,
    current_user: User = Depends(require_teacher),
    session: Session = Depends(get_session),
) -> PresentationResponse:
    """Update slide-to-video associations/mappings for a presentation (Teacher only)."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    presentation = session.get(Presentation, presentation_id)
    if not presentation or presentation.course_id != course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presentation not found in this course")

    # Map of slide_index -> mapping item
    mapping_dict = {m.slide_index: m for m in data.mappings}

    slides = list(presentation.slides)
    for idx, slide in enumerate(slides):
        s_idx = slide.get("index", idx + 1)
        # Match by 0-indexed idx or 1-indexed s_idx
        m = mapping_dict.get(idx) if idx in mapping_dict else mapping_dict.get(s_idx)
        if m is not None:
            slide["video_id"] = m.video_id
            slide["video_start"] = m.video_start
            slide["video_end"] = m.video_end

    presentation.slides = slides
    session.add(presentation)
    session.commit()
    session.refresh(presentation)
    return build_presentation_response(presentation)
