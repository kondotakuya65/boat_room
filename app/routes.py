from fastapi import APIRouter, HTTPException, Query
from typing import List

from .models import AvailabilityResult
from .availability import is_free_for_range
from .sheets.parsers import get_all_rooms_with_occupied_ranges, refresh_all
from .config import get_boat_link, get_room_link

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/refresh")
async def refresh():
    refresh_all()
    return {"status": "refreshed"}


@router.get("/availability", response_model=List[AvailabilityResult])
async def availability(start: str = Query(..., description="YYYY/MM/DD"), end: str = Query(..., description="YYYY/MM/DD")):
    if len(start) != 10 or len(end) != 10:
        raise HTTPException(status_code=400, detail="Dates must be YYYY/MM/DD")

    rooms = get_all_rooms_with_occupied_ranges()
    results: List[AvailabilityResult] = []
    for room in rooms:
        if is_free_for_range(start, end, room["occupied"]):
            boat_name = room["boat_name"]
            room_name = room["room_name"]
            results.append(AvailabilityResult(
                start=start,
                boat_name=boat_name,
                boat_link=get_boat_link(boat_name),
                room_name=room_name,
                room_link=room.get("room_link") or get_room_link(boat_name, room_name)
            ))
    # sort by boat then room
    results.sort(key=lambda r: (r.boat_name.lower(), r.room_name.lower()))
    return results
