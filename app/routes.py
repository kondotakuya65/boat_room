from fastapi import APIRouter, HTTPException, Query
from typing import List

from .models import AvailabilityResult
from .availability import is_free_for_range, find_available_start_dates
from .sheets.parsers import get_all_rooms_with_occupied_ranges, refresh_all
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


@router.get("/availability", response_model=List[AvailabilityResult])
async def availability(start: str = Query(..., description="YYYY/MM/DD"), end: str = Query(..., description="YYYY/MM/DD")):
    if len(start) != 10 or len(end) != 10:
        raise HTTPException(status_code=400, detail="Dates must be YYYY/MM/DD")

    rooms = get_all_rooms_with_occupied_ranges()
    
    # Collect all unique start dates from all rooms (these are the actual start dates in the sheet)
    all_sheet_start_dates = set()
    for room in rooms:
        for occupied_start, occupied_end in room["occupied"]:
            from datetime import datetime
            start_date = datetime.strptime(occupied_start, "%Y/%m/%d").date()
            all_sheet_start_dates.add(start_date)
    
    results: List[AvailabilityResult] = []
    for room in rooms:
        # Find all available start dates within the query range
        available_dates = find_available_start_dates(start, end, room["occupied"], all_sheet_start_dates)
        
        # For each available date, create a result
        for available_date in available_dates:
            boat_name = room["boat_name"]
            room_name = room["room_name"]
            results.append(AvailabilityResult(
                start=available_date,
                boat_name=boat_name,
                boat_link=get_boat_link(boat_name),
                room_name=room_name,
                room_link=room.get("room_link") or get_room_link(boat_name, room_name)
            ))
    results.sort(key=lambda r: (r.start, r.boat_name.lower(), r.room_name.lower()))
    return results
