import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pptx
from pptx import Presentation as PptxPresentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def normalize_slide_embed_url(url: str) -> str:
    """
    Normalizes slide presentation URLs from various providers (Google Slides,
    OneDrive/SharePoint, Canva, SlideShare) into clean, embeddable iframe URLs.
    """
    if not url:
        return ""
    url = url.strip()

    # Extract src if full <iframe> tag was pasted
    iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', url, re.IGNORECASE)
    if iframe_match:
        url = iframe_match.group(1).strip()

    # Google Slides /presentation/d/e/.../pub
    gs_pub_match = re.search(r"docs\.google\.com/presentation/d/e/([a-zA-Z0-9_-]+)", url)
    if gs_pub_match:
        deck_id = gs_pub_match.group(1)
        return f"https://docs.google.com/presentation/d/e/{deck_id}/embed?start=false&loop=false&delayms=3000"

    # Google Slides /presentation/d/.../edit or /pub
    gs_match = re.search(r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)", url)
    if gs_match:
        deck_id = gs_match.group(1)
        return f"https://docs.google.com/presentation/d/{deck_id}/embed?start=false&loop=false&delayms=3000"

    # Canva presentation view -> embed
    canva_match = re.search(r"(canva\.com/design/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/view)", url)
    if canva_match and "?embed" not in url:
        return f"https://www.{canva_match.group(1)}?embed"

    # SlideShare embed standardizer
    if "slideshare.net" in url and "embed_code" not in url:
        return url

    return url


def parse_pptx_file(
    file_path: Path,
    pres_id: str,
    images_base_dir: Path,
    media_url_prefix: str = "/media/presentations",
) -> Dict[str, Any]:
    """
    Parses a .pptx file, extracting slides, titles, bullet points, text blocks,
    tables, speaker notes, and embedded images.
    Saves extracted images to disk and generates web-accessible URLs.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"PPTX file not found: {file_path}")

    prs = PptxPresentation(str(file_path))

    # Calculate aspect ratio
    width = prs.slide_width
    height = prs.slide_height
    ratio_str = "16:9"
    if width and height:
        ratio = width / height
        if abs(ratio - (4 / 3)) < 0.1:
            ratio_str = "4:3"
        elif abs(ratio - (16 / 9)) < 0.1:
            ratio_str = "16:9"
        elif abs(ratio - (16 / 10)) < 0.1:
            ratio_str = "16:10"

    # Prepare images output directory: images_base_dir / pres_id / images
    pres_images_dir = images_base_dir / pres_id / "images"
    pres_images_dir.mkdir(parents=True, exist_ok=True)

    slides_data: List[Dict[str, Any]] = []

    for s_idx, slide in enumerate(prs.slides, start=1):
        # 1. Slide Title
        slide_title = ""
        try:
            if slide.shapes.title and slide.shapes.title.text:
                slide_title = slide.shapes.title.text.strip()
        except Exception:
            slide_title = ""

        # 2. Speaker Notes
        notes_text = ""
        try:
            if slide.has_notes_slide and slide.notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            notes_text = ""

        text_blocks: List[Dict[str, Any]] = []
        tables_data: List[Dict[str, Any]] = []
        images_data: List[Dict[str, Any]] = []
        img_counter = 0

        # Helper to inspect shapes (including grouped shapes)
        def process_shape(shape):
            nonlocal slide_title, img_counter

            # Text shape
            if shape.has_text_frame:
                is_title_shape = False
                try:
                    is_title_shape = (shape == slide.shapes.title)
                except Exception:
                    pass

                # If slide_title wasn't found yet and shape has prominent text
                if not slide_title and shape.text_frame.text.strip():
                    lines = [ln.strip() for ln in shape.text_frame.text.split("\n") if ln.strip()]
                    if lines:
                        slide_title = lines[0]

                for para in shape.text_frame.paragraphs:
                    p_text = para.text.strip()
                    if not p_text:
                        continue
                    # Avoid repeating exact slide title if already shown
                    if is_title_shape and p_text == slide_title:
                        continue

                    level = getattr(para, "level", 0) or 0
                    is_bold = False
                    try:
                        is_bold = any(run.font and run.font.bold for run in para.runs)
                    except Exception:
                        pass

                    text_blocks.append({
                        "text": p_text,
                        "level": level,
                        "is_bold": is_bold,
                        "is_title": is_title_shape,
                    })

            # Table shape
            if shape.has_table:
                try:
                    table = shape.table
                    rows_raw: List[List[str]] = []
                    for row in table.rows:
                        row_cells = [cell.text.strip() for cell in row.cells]
                        rows_raw.append(row_cells)
                    if rows_raw:
                        headers = rows_raw[0]
                        body_rows = rows_raw[1:] if len(rows_raw) > 1 else []
                        tables_data.append({
                            "headers": headers,
                            "rows": body_rows,
                        })
                except Exception:
                    pass

            # Image shape
            is_pic = False
            try:
                is_pic = (shape.shape_type == MSO_SHAPE_TYPE.PICTURE) or (hasattr(shape, "image") and shape.image is not None)
            except Exception:
                pass

            if is_pic:
                try:
                    img = shape.image
                    img_counter += 1
                    ext = img.ext or "png"
                    if ext.lower() in ("jpeg", "jpg"):
                        ext = "jpg"
                    elif ext.lower() not in ("png", "jpg", "gif", "webp", "svg", "bmp"):
                        ext = "png"

                    img_filename = f"slide_{s_idx}_img_{img_counter}.{ext}"
                    img_dest = pres_images_dir / img_filename
                    with open(img_dest, "wb") as f:
                        f.write(img.blob)

                    img_web_url = f"{media_url_prefix}/{pres_id}/images/{img_filename}"
                    images_data.append({
                        "url": img_web_url,
                        "filename": img_filename,
                        "content_type": img.content_type or f"image/{ext}",
                    })
                except Exception:
                    pass

            # Grouped shapes
            if hasattr(shape, "shapes"):
                for sub_shape in shape.shapes:
                    process_shape(sub_shape)

        for shape in slide.shapes:
            process_shape(shape)

        if not slide_title:
            slide_title = f"Slide {s_idx}"

        slides_data.append({
            "index": s_idx,
            "title": slide_title,
            "notes": notes_text or None,
            "text_blocks": text_blocks,
            "tables": tables_data,
            "images": images_data,
        })

    return {
        "slide_count": len(slides_data),
        "aspect_ratio": ratio_str,
        "slides": slides_data,
    }
