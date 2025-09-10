from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from .models import AvailabilityResult
from .availability import is_free_for_range, find_available_start_dates
from .sheets.parsers import get_all_rooms_with_occupied_ranges, get_rooms_with_occupied_ranges_for_boat, refresh_all, get_lamain_sheet_start_dates
from .config import get_boat_link, get_room_link, BOAT_CATALOG
from .sheets.sampler import download_samples_for_spreadsheet
from .sheets.color_dump import dump_worksheet_colors

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/refresh")
async def refresh():
    refresh_all()
    return {"status": "refreshed"}


@router.post("/sample")
async def sample(boat: str = Query(..., description="Boat name as in catalog")):
    boat_info = BOAT_CATALOG.get(boat)
    if not boat_info:
        raise HTTPException(status_code=404, detail="Boat not found")
    sheet_link = boat_info.get("sheet_link")
    if not sheet_link:
        raise HTTPException(status_code=400, detail="No sheet_link for this boat")
    try:
        saved = download_samples_for_spreadsheet(sheet_link, boat)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sample: {e}")
    return {"saved": saved}


@router.post("/color-dump")
async def color_dump(
    boat: str = Query(..., description="Boat name as in catalog"),
    worksheet: str = Query(..., description="Worksheet title, e.g., OPEN TRIP"),
):
    boat_info = BOAT_CATALOG.get(boat)
    if not boat_info:
        raise HTTPException(status_code=404, detail="Boat not found")
    sheet_link = boat_info.get("sheet_link")
    if not sheet_link:
        raise HTTPException(status_code=400, detail="No sheet_link for this boat")
    try:
        dest = dump_worksheet_colors(sheet_link, worksheet, boat)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to dump colors: {e}")
    return {"saved": dest}


@router.get("/boats")
async def list_boats():
    boats = []
    for name, info in BOAT_CATALOG.items():
        boats.append({
            "name": name,
            "boat_link": info.get("boat_link")
        })
    # Stable order
    boats.sort(key=lambda b: b["name"].lower())
    return boats


@router.get("/availability", response_model=List[AvailabilityResult])
async def availability(
    start: str = Query(..., description="YYYY/MM/DD"),
    end: str = Query(..., description="YYYY/MM/DD"),
    boat: str | None = Query(None, description="Optional boat name to limit parsing"),
):
    if len(start) != 10 or len(end) != 10:
        raise HTTPException(status_code=400, detail="Dates must be YYYY/MM/DD")

    print(f"[ROUTES] Getting rooms for boat: {boat}")
    rooms = get_all_rooms_with_occupied_ranges() if not boat else get_rooms_with_occupied_ranges_for_boat(boat)
    print(f"[ROUTES] Got {len(rooms)} rooms")
    
    # Start with empty set - we'll populate it from parser sheet dates
    all_sheet_start_dates = set()
    
    # For SIP 1, also add all sheet start dates (including available ones)
    if boat == "SIP 1":
        from .sheets.sip1_parser import get_sip1_all_sheet_start_dates
        sip1_sheet_dates = get_sip1_all_sheet_start_dates("SIP 1")
        all_sheet_start_dates.update(sip1_sheet_dates)
    
    # For KLM Arfisyana, also add all sheet start dates (including available ones)
    if boat == "KLM Arfisyana":
        from .sheets.arfisyana_parser import get_arfisyana_all_sheet_start_dates
        arfisyana_sheet_dates = get_arfisyana_all_sheet_start_dates("KLM Arfisyana")
        all_sheet_start_dates.update(arfisyana_sheet_dates)

    # For Barakati, also add all sheet start dates (including available ones)
    if boat == "Barakati":
        from .sheets.barakati_parser import get_barakati_all_sheet_start_dates
        barakati_sheet_dates = get_barakati_all_sheet_start_dates("Barakati")
        all_sheet_start_dates.update(barakati_sheet_dates)
    
    # For Lamain Voyages I, also add all sheet start dates (including available ones)
    if boat == "LaMain Voyages I":
        from .sheets.open_trip_parser import parse_open_trip_from_sheets
        _, lamain_sheet_dates = parse_open_trip_from_sheets("LaMain Voyages I")
        all_sheet_start_dates.update(lamain_sheet_dates)
    
    results: List[AvailabilityResult] = []
    for room in rooms:
        boat_name = room["boat_name"]
        room_name = room["room_name"]
        
        # Special handling for calendar-style boats that expose available_dates directly
        if room.get("available_dates") is not None:
            available_dates = room.get("available_dates", [])
            
            # Filter by query range
            from datetime import datetime
            request_start_date = datetime.strptime(start, "%Y/%m/%d").date()
            request_end_date = datetime.strptime(end, "%Y/%m/%d").date()
            
            for available_date in available_dates:
                if request_start_date <= available_date <= request_end_date:
                    results.append(AvailabilityResult(
                        start=available_date.strftime("%Y/%m/%d"),
                        boat_name=boat_name,
                        boat_link=get_boat_link(boat_name),
                        room_name=room_name,
                        room_link=room.get("room_link") or get_room_link(boat_name, room_name)
                    ))
        else:
            # Standard logic for other boats
            print(f"[ROUTES] Processing room: {room_name} (boat: {boat_name})")
            print(f"[ROUTES] Room has {len(room['occupied'])} occupied periods")
            print(f"[ROUTES] Using {len(all_sheet_start_dates)} total sheet start dates")
            available_dates = find_available_start_dates(start, end, room["occupied"], all_sheet_start_dates)
            print(f"[ROUTES] Found {len(available_dates)} available dates for {room_name}")
            
            # For each available date, create a result
            for available_date in available_dates:
                results.append(AvailabilityResult(
                    start=available_date,
                    boat_name=boat_name,
                    boat_link=get_boat_link(boat_name),
                    room_name=room_name,
                    room_link=room.get("room_link") or get_room_link(boat_name, room_name)
                ))
    results.sort(key=lambda r: (r.start, r.boat_name.lower(), r.room_name.lower()))
    print(f"[ROUTES] Returning {len(results)} total results")
    return results


class AvailabilityRequest(BaseModel):
    start: str
    end: str
    boat: Optional[str] = None


@router.post("/availability", response_model=List[AvailabilityResult])
async def availability_post(body: AvailabilityRequest):
    print(f"[API] POST /availability called with start={body.start}, end={body.end}, boat={body.boat}")
    result = await availability(start=body.start, end=body.end, boat=body.boat)
    print(f"[API] Returning {len(result)} results")
    return result
