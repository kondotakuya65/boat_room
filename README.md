Boat Room Availability - Setup and Guide

## Update Google Sheet Links

- File: `app/config.py`
- Section: `BOAT_CATALOG`
- For each boat, update `sheet_link` (Google Sheets URL) and optional `boat_link`.
- Room links: If cells have hyperlinks, the parsers prefer those automatically. Otherwise, the backend falls back to `rooms[room_name]["room_link"]` in `BOAT_CATALOG`.

Steps:
1. Open `app/config.py`.
2. Find the boat entry (e.g., `"Kanha Loka"`, `"LaMain Voyages I"`, `"Sehat Elona from Lombok"`).
3. Replace `sheet_link` with the correct Google Sheet URL.
4. If needed, adjust room names and `room_link` values to match the sheet labels.

Notes:
- Keep room names consistent with the sheet (parsers include canonicalization).
- No need to touch parsers for simple link changes.

## Run Locally

Prereqs:
- Python 3.10+
- Google credentials set up for Sheets API (Service Account recommended)

Install:
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Environment:
- Place your Google Service Account JSON key and set env var:
  - `GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json`

Start server:
```bash
uvicorn app.routes:app --reload --port 8000
```

Open UI:
- Browser: `http://localhost:8000`

API:
- `GET /boats` → list of boats
- `POST /availability` with JSON: `{ "start": "YYYY/MM/DD", "end": "YYYY/MM/DD", "boat": "<boat name or 'all'>" }`

## Deploy

Common options:
- Docker (recommended)
- Bare VM / systemd
- PaaS (Railway/Render/Fly.io/Heroku-like)

Docker quickstart:
1. Create `Dockerfile` (Python base, copy app, install reqs, expose 8000, run uvicorn).
2. Build: `docker build -t boat-room .`
3. Run: `docker run -p 8000:8000 -e GOOGLE_APPLICATION_CREDENTIALS=/app/key.json -v /abs/path/key.json:/app/key.json boat-room`

Systemd (sketch):
- Use a virtualenv and a unit that exports `GOOGLE_APPLICATION_CREDENTIALS` and runs uvicorn as a service.

Secrets & creds:
- Mount service-account key; avoid committing it.
- Restrict Sheet sharing to that service account.

## Parser Notes & Tips

- Kanha: OT bands via border detection; latest fix adds fallback so last month band is included.
- LaMain: Aggregates "Bern" from its sharing sub-rooms; returns single "Bern".
- Barakati/El Rora/Sehat: Use Sheets API v4 merges; availability considers merged ranges.
- Sehat fixed-block mode: each section after header uses rows counts: 4/4/4/6/4/4.

Performance:
- Prefer single Sheets API fetch per parser; avoid redundant calls.
- Cache per-request if needed; avoid global mutable caches across reloads.

Debugging:
- Add prints around date-section detection and month spans when troubleshooting.
- If availability looks off at month-ends, verify border data and fallback logic.

FAQ:
- Q: Boat names with spaces? A: Use `/availability` POST JSON; UI already handles it.
- Q: Hyperlinks missing? A: Cell links are preferred; else config `room_link` is used.
- Q: Merged cells not detected? A: Ensure v4 API is used and service account has access.

# Boat Room Availability

Simple FastAPI app to find free boat rooms across 12 Google Sheets.

## Prerequisites
- Python 3.11+
- `api_key.json` service account credentials in project root
- Share each Google Sheet with the service account email

## Setup (PowerShell)
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GOOGLE_APPLICATION_CREDENTIALS="api_key.json"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/` in your browser.

## API
- GET `/availability?start=YYYY/MM/DD&end=YYYY/MM/DD`
- POST `/refresh` (placeholder, no-op since no cache)
- GET `/health`

## Implementing parsers
Edit `app/sheets/parsers.py` functions (`parser_boat_1`..`parser_boat_12`). Each must return a list of dict items with keys:
```python
{
    "boat_name": str,
    "boat_link": str | None,
    "room_name": str,
    "room_link": str | None,
    "occupied": [("YYYY/MM/DD", "YYYY/MM/DD"), ...],  # end exclusive
}
```
Bookings are full-day, end exclusive.

## Notes
- Dates use format `YYYY/MM/DD` without timezone.
- Sorting is by boat then room.
- No caching by design; reads Sheets on each request.
