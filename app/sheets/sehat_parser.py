#!/usr/bin/env python3

from datetime import datetime, date
from typing import List, Dict, Tuple
import re

from .client import get_gspread_client, get_sheets_service
from .color_dump import get_worksheet_colors


def _normalize_status(val: str) -> str:
    return (val or "").strip().upper()


def _is_available_status(val: str) -> bool:
    s = _normalize_status(val)
    # Available if empty, "AVAILABLE", or any status that's not "BOOKED"
    return s == "" or s == "AVAILABLE" or (s != "BOOKED" and s != "FULLY BOOKED")


def _parse_departure(text: str, fallback_year: int) -> date | None:
    """Parse strings like 'APRIL 12TH', 'MAY 3RD', 'NOVEMBER 1ST', etc."""
    if not text:
        return None
    t = text.strip().upper()
    # Extract month word and day number
    m = re.search(r"([A-Z]+)\s+(\d{1,2})", t)
    if not m:
        return None
    month_word = m.group(1)
    day = int(m.group(2))
    month_map = {
        "JAN": 1, "JANUARY": 1,
        "FEB": 2, "FEBRUARY": 2,
        "MAR": 3, "MARCH": 3,
        "APR": 4, "APRIL": 4,
        "MAY": 5,
        "JUN": 6, "JUNE": 6,
        "JUL": 7, "JULY": 7,
        "AUG": 8, "AUGUST": 8,
        "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
        "OCT": 10, "OCTOBER": 10,
        "NOV": 11, "NOVEMBER": 11,
        "DEC": 12, "DECEMBER": 12,
    }
    month = None
    for key, num in month_map.items():
        if key in month_word:
            month = num
            break
    if not month:
        return None
    try:
        return date(fallback_year, month, day)
    except ValueError:
        return None


def _find_all_departure_rows(rows: List[List[str]]) -> List[Tuple[int, date | None, date | None]]:
    """Find ALL rows that contain departure dates"""
    departure_rows = []
    for i, row in enumerate(rows):
        left_label = (row[0] if len(row) > 0 else "").strip()
        right_label = (row[11] if len(row) > 11 else "").strip()
        left_date = _parse_departure(left_label, 2025)
        right_date = _parse_departure(right_label, 2025)
        if left_date or right_date:
            departure_rows.append((i, left_date, right_date))
    return departure_rows

def _find_room_type_headers(rows: List[List[str]]) -> List[int]:
    """Find ALL rows that contain 'ROOM TYPE' headers"""
    header_rows = []
    for i, row in enumerate(rows):
        if len(row) > 0 and (row[0] or '').strip().upper() == "ROOM TYPE":
            header_rows.append(i)
    return header_rows


def _is_cell_in_merged_range(row_idx: int, col_idx: int, merged_ranges: List[Dict]) -> bool:
    """Check if a cell is part of any merged range"""
    for merge in merged_ranges:
        merge_start_row = merge.get('startRowIndex', 0)
        merge_end_row = merge.get('endRowIndex', 0)
        merge_start_col = merge.get('startColumnIndex', 0)
        merge_end_col = merge.get('endColumnIndex', 0)
        
        if (merge_start_row <= row_idx < merge_end_row and
            merge_start_col <= col_idx < merge_end_col):
            return True
    return False


def _get_merged_range_status(row_idx: int, col_idx: int, merged_ranges: List[Dict], rows: List[List[str]]) -> str:
    """Get the status from a merged range. Returns the status from the first cell of the merged range."""
    for merge in merged_ranges:
        merge_start_row = merge.get('startRowIndex', 0)
        merge_end_row = merge.get('endRowIndex', 0)
        merge_start_col = merge.get('startColumnIndex', 0)
        merge_end_col = merge.get('endColumnIndex', 0)
        
        if (merge_start_row <= row_idx < merge_end_row and
            merge_start_col <= col_idx < merge_end_col):
            # This cell is part of a merged range, get status from the first cell
            if (merge_start_row < len(rows) and 
                merge_start_col < len(rows[merge_start_row])):
                return (rows[merge_start_row][merge_start_col] or "").strip()
    return ""

def _get_merged_room_statuses(row_idx: int, col_idx: int, merged_ranges: List[Dict], rows: List[List[str]]) -> List[str]:
    """Get all statuses from a merged room name range. Returns list of statuses from all rows in the merged range."""
    # Find all merged ranges that contain this cell
    relevant_merges = []
    for merge in merged_ranges:
        merge_start_row = merge.get('startRowIndex', 0)
        merge_end_row = merge.get('endRowIndex', 0)
        merge_start_col = merge.get('startColumnIndex', 0)
        merge_end_col = merge.get('endColumnIndex', 0)
        
        if (merge_start_row <= row_idx < merge_end_row and
            merge_start_col <= col_idx < merge_end_col):
            relevant_merges.append(merge)
    
    if not relevant_merges:
        return []
    
    # Get the room name from the first row of the first merge
    first_merge = relevant_merges[0]
    first_row = first_merge.get('startRowIndex', 0)
    room_name = ""
    if first_row < len(rows) and len(rows[first_row]) > col_idx:
        room_name = (rows[first_row][col_idx] or "").strip()
    
    if not room_name:
        return []
    
    # Find all consecutive merged ranges with the same room name
    all_merges = []
    for merge in merged_ranges:
        merge_start_row = merge.get('startRowIndex', 0)
        merge_end_row = merge.get('endRowIndex', 0)
        merge_start_col = merge.get('startColumnIndex', 0)
        merge_end_col = merge.get('endColumnIndex', 0)
        
        if (merge_start_col <= col_idx < merge_end_col and
            merge_start_row < len(rows) and len(rows[merge_start_row]) > col_idx):
            merge_room_name = (rows[merge_start_row][col_idx] or "").strip()
            if merge_room_name == room_name:
                all_merges.append(merge)
    
    # Sort merges by start row
    all_merges.sort(key=lambda x: x.get('startRowIndex', 0))
    
    # Get statuses from all consecutive merges
    statuses = []
    for merge in all_merges:
        merge_start_row = merge.get('startRowIndex', 0)
        merge_end_row = merge.get('endRowIndex', 0)
        for r in range(merge_start_row, merge_end_row):
            if r < len(rows) and len(rows[r]) > col_idx + 2:  # col_idx + 2 for status column
                status = (rows[r][col_idx + 2] or "").strip()
                statuses.append(status)
    
    return statuses

def _get_room_statuses_from_range(start_row: int, end_row: int, col_idx: int, rows: List[List[str]]) -> List[str]:
    """Get all statuses from a specific row range. Returns list of statuses from all rows in the range."""
    statuses = []
    for r in range(start_row, end_row):
        if r < len(rows) and len(rows[r]) > col_idx + 2:  # col_idx + 2 for status column
            status = (rows[r][col_idx + 2] or "").strip()
            statuses.append(status)
    return statuses

def _get_merged_room_range(row_idx: int, col_idx: int, merged_ranges: List[Dict]) -> tuple:
    """Get the row range for a merged room name. Returns (start_row, end_row) in 1-based indexing."""
    for merge in merged_ranges:
        merge_start_row = merge.get('startRowIndex', 0)
        merge_end_row = merge.get('endRowIndex', 0)
        merge_start_col = merge.get('startColumnIndex', 0)
        merge_end_col = merge.get('endColumnIndex', 0)
        
        if (merge_start_row <= row_idx < merge_end_row and
            merge_start_col <= col_idx < merge_end_col):
            # Return 1-based row indices
            return (merge_start_row + 1, merge_end_row)
    return (row_idx + 1, row_idx + 1)  # Single row, 1-based


def _canonicalize_room_name(sheet_room: str, config_rooms: List[str]) -> Tuple[str, str | None]:
    """Map sheet room label to a canonical config room name (case-insensitive), and return (canonical, keyword).
    Falls back to sheet name if no match.
    """
    label = (sheet_room or "").strip()
    upper = label.upper()
    # Exact case-insensitive match
    for cfg in config_rooms:
        if upper == cfg.upper():
            return cfg, cfg
    # Keyword-based mapping
    key_map = {
        "LUXURY": "Luxury Cabin",
        "GRAND DELUXE": "Grand Deluxe",
        "DELUXE TWIN": "Deluxe Twin",
        "DELUXE TRIPLE": "Deluxe Triple",
        "REGULAR CABIN 1": "Regular Cabin 1",
        "REGULAR CABIN 2": "Regular Cabin 2",
    }
    for key, canonical in key_map.items():
        if key in upper:
            # Ensure canonical exists in config
            for cfg in config_rooms:
                if cfg.upper() == canonical.upper():
                    return cfg, cfg
            return canonical, canonical
    return label, None


def parse_sehat_from_sheets(boat_name: str) -> List[Dict]:
    from ..config import BOAT_CATALOG, get_room_link

    if boat_name not in BOAT_CATALOG:
        return []

    sheet_link = BOAT_CATALOG[boat_name].get("sheet_link")
    if not sheet_link:
        return []

    # Determine which worksheets to include based on boat_name
    target_prefix = None
    upper_boat = boat_name.strip().upper()
    if "FROM LOMBOK" in upper_boat:
        target_prefix = "LOMBOK-"
    elif "FROM LABUAN BAJO" in upper_boat or "LABUAN BAJO" in upper_boat:
        target_prefix = "LABUAN BAJO-"

    # Determine config order and link mapping
    config_rooms_order = list((BOAT_CATALOG[boat_name].get("rooms") or {}).keys())

    gc = get_gspread_client()
    sheet = gc.open_by_url(sheet_link)

    results: List[Dict] = []

    for ws in sheet.worksheets():
        ws_title_upper = (ws.title or '').strip().upper()
        if target_prefix and not ws_title_upper.startswith(target_prefix):
            continue
        rows = ws.get('A1:ZZ1000')
        
        # Get merged cell information from Google Sheets API v4
        service = get_sheets_service()
        merged_ranges = []
        try:
            result = service.spreadsheets().get(
                spreadsheetId=sheet.id,
                ranges=[f'{ws.title}!A1:ZZ1000'],
                includeGridData=False
            ).execute()
            
            if 'sheets' in result and len(result['sheets']) > 0:
                sheet_data = result['sheets'][0]
                if 'merges' in sheet_data:
                    merged_ranges = sheet_data['merges']
        except Exception as e:
            # Fallback if API call fails
            pass

        # Aggregate by canonical name
        room_to_dates: Dict[str, List[date]] = {}
        room_to_link: Dict[str, str | None] = {}
        
        # Find all departure rows and room type headers
        departure_rows = _find_all_departure_rows(rows)
        header_rows = _find_room_type_headers(rows)
        
        # Process each section
        for i, (dep_row_idx, left_date, right_date) in enumerate(departure_rows):
            # Find the next departure row to determine section end
            next_dep_row_idx = departure_rows[i + 1][0] if i + 1 < len(departure_rows) else len(rows)
            
            # Look for ROOM TYPE header after this departure
            room_type_row = None
            for header_row in header_rows:
                if dep_row_idx < header_row < next_dep_row_idx:
                    room_type_row = header_row
                    break
            
            if room_type_row:
                # Analyze room data from ROOM TYPE header to next departure using fixed layout
                room_data_start = room_type_row + 1
                room_data_end = next_dep_row_idx

                # Fixed room blocks per section (rows counts)
                room_blocks = [
                    ("LUXURY CABIN", 4),
                    ("GRAND DELUXE", 4),
                    ("DELUXE TWIN", 4),
                    ("DELUXE TRIPLE", 6),
                    ("REGULAR CABIN 1", 4),
                    ("REGULAR CABIN 2", 4),
                ]

                # Helper to process one side (left or right)
                def _process_side(start_col: int, status_col: int, dep_date: date | None):
                    if not dep_date:
                        return
                    offset = 0
                    for room_label, count in room_blocks:
                        start_r = room_data_start + offset
                        end_r = start_r + count
                        # Clamp to section end just in case
                        if start_r >= room_data_end:
                            break
                        if end_r > room_data_end:
                            end_r = room_data_end
                        # Collect statuses across the block
                        statuses: List[str] = []
                        for rr in range(start_r, end_r):
                            if rr < len(rows) and len(rows[rr]) > status_col:
                                statuses.append((rows[rr][status_col] or "").strip())
                            else:
                                statuses.append("")
                        # Canonicalize room name to config name
                        canonical, key = _canonicalize_room_name(room_label, config_rooms_order)
                        if any(_is_available_status(s) for s in statuses):
                            room_to_dates.setdefault(canonical, []).append(dep_date)
                        if key:
                            room_to_link.setdefault(canonical, get_room_link(boat_name, key))
                        offset += count

                # Left side (columns A: name col 0, status col 2)
                _process_side(0, 2, left_date)
                # Right side (columns L: name col 11, status col 13)
                _process_side(11, 13, right_date)

        for canonical_name, dates in room_to_dates.items():
            link = room_to_link.get(canonical_name)
            results.append({
                "boat_name": boat_name,
                "room_name": canonical_name,
                "occupied": [],
                "available_dates": sorted(set(dates)),
                "room_link": link,
            })

    return results
