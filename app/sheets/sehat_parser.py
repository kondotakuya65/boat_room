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
    return s == "" or s == "AVAILABLE"


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


def _find_block_headers(rows: List[List[str]], start_idx: int) -> Tuple[int | None, int | None, date | None, date | None]:
    """Find the next block starting at or after start_idx.
    Returns (header_row_idx, columns_header_row_idx, left_date, right_date) or (None, None, None, None).
    A block is identified by a row that contains two departure labels in far left and far right columns,
    followed by a columns header row containing two sets of 'ROOM TYPE', 'NAME', 'STATUS' ...
    """
    i = start_idx
    while i < len(rows) - 1:
        row = rows[i]
        # Detect a departure row if it has two tokens with a month and day, typically placed with gap
        left_label = (row[0] if len(row) > 0 else "").strip()
        right_label = (row[11] if len(row) > 11 else "").strip()
        left_date = _parse_departure(left_label, 2025)
        right_date = _parse_departure(right_label, 2025)
        if left_date or right_date:
            # Next row should be the columns header row
            hdr = rows[i + 1] if i + 1 < len(rows) else []
            # Expect 'ROOM TYPE' at col 0 and col 11
            if (len(hdr) > 0 and (hdr[0] or '').strip().upper() == "ROOM TYPE") and (len(hdr) > 11 and (hdr[11] or '').strip().upper() == "ROOM TYPE"):
                return i, i + 1, left_date, right_date
        i += 1
    return None, None, None, None


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
        # colors not strictly needed (status cell determines availability), but load if style relies on color in future
        # service = get_sheets_service()
        # colors = get_worksheet_colors(service, sheet.id, ws.title)

        idx = 0
        # Aggregate by canonical name
        room_to_dates: Dict[str, List[date]] = {}
        room_to_link: Dict[str, str | None] = {}
        while True:
            header_row_idx, cols_header_idx, left_date, right_date = _find_block_headers(rows, idx)
            if header_row_idx is None:
                break
            r = cols_header_idx + 1

            # Aggregate statuses for each room across continuation rows within this block
            left_room_current = None
            right_room_current = None
            left_room_statuses: Dict[str, List[str]] = {}
            right_room_statuses: Dict[str, List[str]] = {}

            while r < len(rows):
                row = rows[r]
                if not any((c or "").strip() for c in row):
                    break
                if _parse_departure((row[0] if len(row) > 0 else ""), 2025) or _parse_departure((row[11] if len(row) > 11 else ""), 2025):
                    break

                left_room_raw = (row[0] if len(row) > 0 else "").strip()
                left_status = (row[2] if len(row) > 2 else "").strip()
                right_room_raw = (row[11] if len(row) > 11 else "").strip()
                right_status = (row[13] if len(row) > 13 else "").strip()

                if left_room_raw:
                    left_room_current = left_room_raw
                if left_room_current is not None:
                    left_room_statuses.setdefault(left_room_current, []).append(left_status)

                if right_room_raw:
                    right_room_current = right_room_raw
                if right_room_current is not None:
                    right_room_statuses.setdefault(right_room_current, []).append(right_status)

                r += 1

            # Decide availability per room for this block's left and right departures
            if left_date:
                for sheet_room, statuses in left_room_statuses.items():
                    canonical, key = _canonicalize_room_name(sheet_room, config_rooms_order)
                    if any(_is_available_status(s) for s in statuses):
                        room_to_dates.setdefault(canonical, []).append(left_date)
                    if key:
                        room_to_link.setdefault(canonical, get_room_link(boat_name, key))
            if right_date:
                for sheet_room, statuses in right_room_statuses.items():
                    canonical, key = _canonicalize_room_name(sheet_room, config_rooms_order)
                    if any(_is_available_status(s) for s in statuses):
                        room_to_dates.setdefault(canonical, []).append(right_date)
                    if key:
                        room_to_link.setdefault(canonical, get_room_link(boat_name, key))

            idx = r + 1

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
