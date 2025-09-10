import os
import csv
import json
import re
from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional
import calendar

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "APL": 4, "MAY": 5, "JUN": 6, "JUNI": 6,
    "JUL": 7, "JUL ": 7, "AUG": 8, "AGT": 8, "SEPT": 9, "SEP": 9,
    "OCT": 10, "NOV": 11, "DEC": 12, "DES": 12,
}


def _to_year() -> int:
    return 2025


def _normalize_month(label: str) -> Optional[int]:
    if not label:
        return None
    key = label.strip().upper()
    return MONTH_MAP.get(key)


def _clamp_day(year: int, month: int, day: int) -> int:
    if day < 1:
        return 1
    max_day = calendar.monthrange(year, month)[1]
    if day > max_day:
        return max_day
    return day


def _next_month(year: int, month: int) -> Tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _parse_date_range_cell(cell_value: str) -> Optional[Tuple[date, date]]:
    """Parse date range from cell like 'Sept \n12-14' or 'May-Jun\n30-01'"""
    if not cell_value or not cell_value.strip():
        return None
    
    # Split by newline to separate month and date range
    parts = cell_value.strip().split('\n')
    if len(parts) != 2:
        return None
    
    month_part = parts[0].strip()
    date_part = parts[1].strip()
    
    # Parse month(s)
    if '-' in month_part:
        # Cross-month range like "May-Jun"
        start_month, end_month = month_part.split('-')
        start_month_num = _normalize_month(start_month.strip())
        end_month_num = _normalize_month(end_month.strip())
        if not start_month_num or not end_month_num:
            return None
    else:
        # Single month
        month_num = _normalize_month(month_part)
        if not month_num:
            return None
        start_month_num = end_month_num = month_num
    
    # Parse date range
    if '-' in date_part:
        start_day, end_day = date_part.split('-')
        try:
            start_day_num = int(start_day.strip())
            end_day_num = int(end_day.strip())
            
            # Handle cross-month date ranges
            if start_day_num > end_day_num:
                # Cross-month: e.g., "30-01" means 30th of start month to 1st of end month
                start_date = date(2025, start_month_num, _clamp_day(2025, start_month_num, start_day_num))
                end_date = date(2025, end_month_num, _clamp_day(2025, end_month_num, end_day_num)) + timedelta(days=1)
            else:
                # Same month: e.g., "12-14" means 12th to 14th of same month
                start_date = date(2025, start_month_num, _clamp_day(2025, start_month_num, start_day_num))
                end_date = date(2025, start_month_num, _clamp_day(2025, start_month_num, end_day_num)) + timedelta(days=1)
            
            return (start_date, end_date)
        except ValueError:
            return None
    
    return None


def _read_csv_rows(csv_path: str) -> List[List[str]]:
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))


def _read_colors(json_path: str) -> List[List[Dict[str, Optional[float]]]]:
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _is_white(color: Dict[str, Optional[float]]) -> bool:
    if color is None:
        return True
    r = color.get('r'); g = color.get('g'); b = color.get('b')
    return (r is None and g is None and b is None) or (r == 1 and g == 1 and b == 1)


def parse_open_trip_from_sheets(boat_name: str, worksheet_title: str = "OPEN TRIP") -> Tuple[List[Dict], set]:
    """Parse OPEN TRIP data directly from Google Sheets, returns (rooms, all_sheet_start_dates)"""
    from app.config import BOAT_CATALOG
    from app.sheets.client import get_gspread_client, get_sheets_service
    from app.sheets.color_dump import get_worksheet_colors
    
    if boat_name not in BOAT_CATALOG:
        return [], set()
    
    sheet_link = BOAT_CATALOG[boat_name]["sheet_link"]
    if not sheet_link:
        return [], set()
    
    try:
        # Get gspread client and open the sheet
        gc = get_gspread_client()
        sheet = gc.open_by_url(sheet_link)
        worksheet = sheet.worksheet(worksheet_title)
        
        # Get all values from the worksheet
        rows = worksheet.get_all_values()
        
        # Get colors using the sheets service
        sheets_service = get_sheets_service()
        colors = get_worksheet_colors(sheets_service, sheet.id, worksheet_title)
        
        # Parse room data
        rooms = _parse_open_trip_data(rows, colors, boat_name)
        
        # Extract all sheet start dates from the same data
        all_sheet_start_dates = set()
        if len(rows) >= 29:
            date_range_row = rows[28]  # Row 29: Date ranges
            for c, cell_value in enumerate(date_range_row):
                rng = _parse_date_range_cell(cell_value)
                if rng:
                    start_date, end_date = rng
                    all_sheet_start_dates.add(start_date)
        
        return rooms, all_sheet_start_dates
        
    except Exception as e:
        print(f"Error parsing {boat_name} sheet: {e}")
        import traceback
        traceback.print_exc()
        return [], set()


def _parse_open_trip_data(rows: List[List[str]], colors: List[List[Dict]], boat_name: str) -> List[Dict]:
    """Parse OPEN TRIP data from rows and colors arrays"""
    # Focus on rows 29-38 (0-indexed: 28-37)
    # Row 29 (0-indexed: 28): Date ranges like "Sept \n12-14"
    # Rows 30-38 (0-indexed: 29-37): Room data
    
    if len(rows) < 38:  # Need at least 38 rows
        return []
    
    date_range_row = rows[28]  # Row 29: Date ranges
    room_rows = rows[29:38]    # Rows 30-38: Room data
    
    # Parse date ranges from row 29
    col_to_range: Dict[int, Optional[Tuple[date, date]]] = {}
    
    for c, cell_value in enumerate(date_range_row):
        rng = _parse_date_range_cell(cell_value)
        col_to_range[c] = rng

    # Room name mapping - keep BERN children separate
    room_name_map = {
        "PARIS ROOM": "Paris",
        "OSAKA ROOM": "Osaka", 
        "ATHENS ROOM": "Athena",
        "PRAHA ROOM": "Praha",
        "VENICE ROOM": "Venice",
        "BERN ROOM (SHARING) 1": "Bern (sharing) 1",
        "BERN ROOM (SHARING) 2": "Bern (sharing) 2", 
        "BERN ROOM (SHARING) 3": "Bern (sharing) 3",
        "BERN ROOM (SHARING) 4": "Bern (sharing) 4",
    }

    # Track occupied ranges per room (including individual BERN children)
    per_room: Dict[str, set] = {}

    # Process each room row (rows 30-38, 0-indexed: 29-37)
    for r_idx in range(29, 38):  # Rows 30-38 (0-indexed: 29-37)
        if r_idx >= len(rows) or r_idx >= len(colors):
            continue
            
        room_row = rows[r_idx]
        color_row = colors[r_idx]
        
        # Get room name from first column
        room_label = (room_row[0] or '').strip().upper()
        if not room_label or "ROOM" not in room_label:
            continue
            
        # Map to canonical room name
        canonical = room_name_map.get(room_label)
        if not canonical:
            # Try partial match for BERN rooms
            for k, v in room_name_map.items():
                if room_label.startswith(k):
                    canonical = v
                    break
        if not canonical:
            continue
            
        # Initialize bucket for this room
        bucket = per_room.setdefault(canonical, set())
        
        # Check each column for occupied dates
        for c in range(2, min(len(room_row), len(color_row))):  # Start from column 3 (0-indexed: 2)
            rng = col_to_range.get(c)
            if not rng:
                continue
                
            color = color_row[c] if c < len(color_row) else None
            if color is None:
                continue
                
            is_white_color = _is_white(color)
            if not is_white_color:  # Non-white means occupied
                start, end = rng
                bucket.add((start.strftime("%Y/%m/%d"), end.strftime("%Y/%m/%d")))

    # Convert to results
    results: List[Dict] = []
    for room_name, occupied_set in per_room.items():
        # Skip individual Bern sharing children from response; we'll add aggregated "Bern" below
        if room_name.upper().startswith("BERN (SHARING"):
            continue
        occupied = sorted(list(occupied_set))
        results.append({
            "boat_name": boat_name,
            "room_name": room_name,
            "occupied": occupied,
        })

    # Aggregated "Bern" logic:
    # Bern (overall) should be available if ANY Bern (sharing) place is available,
    # and disabled only when ALL Bern (sharing) places are booked for a given range.
    # We model this by marking Bern's occupied ranges as those where all Bern-sharing
    # children are occupied.
    bern_children = [name for name in per_room.keys() if name.upper().startswith("BERN (SHARING)")]
    if bern_children:
        # Count occupancy across children for each (start,end) range
        range_to_count: Dict[Tuple[str, str], int] = {}
        for child in bern_children:
            for rng in per_room.get(child, set()):
                range_to_count[rng] = range_to_count.get(rng, 0) + 1
        # A range is occupied for overall Bern only if ALL children are occupied in that range
        all_children = len(bern_children)
        bern_occupied = sorted([list(rng) for rng, cnt in range_to_count.items() if cnt >= all_children])
        results.append({
            "boat_name": boat_name,
            "room_name": "Bern",
            "occupied": bern_occupied,
        })

    return results


def parse_open_trip_from_files(boat_name: str, worksheet_title: str = "OPEN TRIP") -> List[Dict]:
    """Parse the OPEN TRIP worksheet from local files (for testing/fallback)"""
    # Handle both running from root directory and app directory
    if os.path.exists("data"):
        # Running from root directory
        base_csv = os.path.join("data", "samples", boat_name, f"{worksheet_title}.csv")
        base_json = os.path.join("data", "colors", boat_name, f"{worksheet_title}.json")
    else:
        # Running from app directory
        base_csv = os.path.join("..", "data", "samples", boat_name, f"{worksheet_title}.csv")
        base_json = os.path.join("..", "data", "colors", boat_name, f"{worksheet_title}.json")
    
    rows = _read_csv_rows(base_csv)
    colors = _read_colors(base_json)
    
    return _parse_open_trip_data(rows, colors, boat_name)