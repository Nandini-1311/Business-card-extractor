"""
Business Card Lead Extraction.

Run with:
    uvicorn app.main:app --reload
"""

import io
import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from openpyxl.styles import Font
from starlette.requests import Request

from .db import delete_card_row, get_all_cards, save_card
from .extractor import extract_card

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR.parent / "uploads"
DB_FILE = BASE_DIR.parent / "cards.json"

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_FILE_SIZE_MB = 15
MAX_BATCH_SIZE = 50

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Business Card Lead Extraction")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/files", StaticFiles(directory=UPLOAD_DIR), name="files")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------------------------------------------------------------------------
# JSON registry (tracks upload status per card)
# ---------------------------------------------------------------------------

def _load_db() -> List[dict]:
    if not DB_FILE.exists():
        return []
    with open(DB_FILE, "r") as f:
        return json.load(f)


def _save_db(cards: List[dict]) -> None:
    with open(DB_FILE, "w") as f:
        json.dump(cards, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Extraction: image -> vision model -> MySQL
# ---------------------------------------------------------------------------

def _extract_and_store(card: dict, image_path: Path) -> None:
    """Read one card with the vision model and save it to MySQL. Updates `card` in place."""
    try:
        print(f"[extract] starting: {image_path.name}")
        data, raw = extract_card(str(image_path))
        print(f"[extract] model returned: {data}")
        row_id = save_card(data, image_path=card["stored_filename"], raw_text=raw)
        print(f"[extract] saved to MySQL with id {row_id}")
        card["extracted_fields"] = data
        card["db_id"] = row_id
        card["status"] = "extracted"
        card.pop("error", None)
    except Exception as e:
        traceback.print_exc()
        card["status"] = "failed"
        card["error"] = str(e)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/api/cards")
async def list_cards():
    cards = _load_db()
    cards.sort(key=lambda c: c["uploaded_at"], reverse=True)
    return {"cards": cards, "count": len(cards)}


@app.post("/api/upload")
async def upload_cards(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files were sent.")
    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files in one batch (max {MAX_BATCH_SIZE}). Split into smaller batches.",
        )

    cards = _load_db()
    results = []

    for upload in files:
        entry = {"original_filename": upload.filename}

        if upload.content_type not in ALLOWED_CONTENT_TYPES:
            entry.update(status="rejected", error=f"Unsupported file type: {upload.content_type}")
            results.append(entry)
            continue

        contents = await upload.read()
        size_mb = len(contents) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            entry.update(status="rejected", error=f"File too large ({size_mb:.1f} MB > {MAX_FILE_SIZE_MB} MB)")
            results.append(entry)
            continue

        card_id = str(uuid.uuid4())
        ext = Path(upload.filename).suffix.lower() or ".jpg"
        stored_name = f"{card_id}{ext}"
        dest_path = UPLOAD_DIR / stored_name

        with open(dest_path, "wb") as f:
            f.write(contents)

        card = {
            "id": card_id,
            "original_filename": upload.filename,
            "stored_filename": stored_name,
            "url": f"/files/{stored_name}",
            "size_bytes": len(contents),
            "content_type": upload.content_type,
            "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "extracted_fields": None,
        }

        # Run the (slow) model call in a worker thread so the server stays responsive.
        await run_in_threadpool(_extract_and_store, card, dest_path)

        cards.append(card)
        results.append(card)

    _save_db(cards)

    accepted = [r for r in results if r.get("status") != "rejected"]
    rejected = [r for r in results if r.get("status") == "rejected"]
    return {"accepted": accepted, "rejected": rejected}


@app.post("/api/cards/{card_id}/extract")
async def retry_extract(card_id: str):
    """Run extraction on a card that is still 'uploaded' or 'failed'."""
    cards = _load_db()
    card = next((c for c in cards if c["id"] == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")
    if card.get("status") == "extracted":
        raise HTTPException(status_code=400, detail="Card is already extracted.")

    await run_in_threadpool(_extract_and_store, card, UPLOAD_DIR / card["stored_filename"])
    _save_db(cards)
    return card


@app.get("/api/export")
async def export_excel():
    rows = await run_in_threadpool(get_all_cards)

    wb = Workbook()
    ws = wb.active
    ws.title = "Business Cards"

    ws.append(["ID", "First Name", "Last Name", "Designation", "Email", "Phone", "Location", "Added On"])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for r in rows:
        ws.append([
            r["id"], r["first_name"], r["last_name"], r["designation"],
            r["email"], r["phone"], r["location"],
            r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "",
        ])

    for col in ws.columns:
        longest = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(longest + 2, 50)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="business_cards.xlsx"'},
    )


@app.delete("/api/cards/{card_id}")
async def delete_card(card_id: str):
    cards = _load_db()
    match = next((c for c in cards if c["id"] == card_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Card not found.")

    file_path = UPLOAD_DIR / match["stored_filename"]
    if file_path.exists():
        file_path.unlink()

    if match.get("db_id"):
        await run_in_threadpool(delete_card_row, match["db_id"])

    cards = [c for c in cards if c["id"] != card_id]
    _save_db(cards)
    return {"deleted": card_id}


@app.get("/api/cards/{card_id}/image")
async def get_card_image(card_id: str):
    cards = _load_db()
    match = next((c for c in cards if c["id"] == card_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Card not found.")
    return FileResponse(UPLOAD_DIR / match["stored_filename"])