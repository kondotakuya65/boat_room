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
