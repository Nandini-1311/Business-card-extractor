# Business Card Lead Extraction — Step 1: Bulk Upload Interface

This is the first slice of the project: a FastAPI web app that lets someone
drag-and-drop (or select) a batch of business card images and stores them,
ready for the extraction step to come.

## What's included

- `app/main.py` — FastAPI backend
  - `GET /` — the upload page
  - `POST /api/upload` — accepts multiple files in one request (`files`, multipart/form-data)
  - `GET /api/cards` — lists everything uploaded so far
  - `DELETE /api/cards/{id}` — removes a card
  - Files are validated (type + size), saved under `uploads/`, and tracked in `cards.json`
    (a placeholder store — swap for Postgres/SQLite once the schema settles)
  - Each card is created with `status: "uploaded"`. The extraction step should update
    that to `"extracted"` and fill in `extracted_fields` once OCR/parsing is wired in.
- `app/templates/index.html`, `app/static/style.css`, `app/static/script.js` — the UI
- `requirements.txt`

## Run it

```bash
cd card_extractor
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000**.

## Notes for the next step (extraction)

- `POST /api/upload` is the natural hook point: after a file is saved, you could
  enqueue an OCR/extraction job (Tesseract, a cloud Vision API, or an LLM call) keyed
  by `card_id`, and have it PATCH the card's `extracted_fields` + `status` when done.
- The registry is a flat JSON file for now (`cards.json`) so this step stays
  dependency-light — happy to swap in SQLite/Postgres + SQLAlchemy once we design
  the lead schema (name, title, company, phone, email, address, etc.).
- Limits (`MAX_FILE_SIZE_MB`, `MAX_BATCH_SIZE`, allowed content types) are constants
  at the top of `main.py` — adjust as needed.
