#!/usr/bin/env python3

from __future__ import annotations

from datetime import date, datetime
from typing import List, Dict, Tuple
import re

from .client import get_gspread_client, get_sheets_service
from .color_dump import get_worksheet_colors, get_worksheet_borders


_MONTH_MAP = {
    "JAN": 1, "JANUARY": 1, "JANUARI": 1,
    "FEB": 2, "FEBRUARY": 2, "FEBUARI": 2,
    "MAR": 3, "MARCH": 3, "MARET": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5, "MEI": 5,
    "JUN": 6, "JUNE": 6, "JUNI": 6,
    "JUL": 7, "JULY": 7, "JULI": 7,
    "AUG": 8, "AUGUST": 8, "AGUSTUS": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "OKTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DECEMBER": 12, "DESEMBER": 12,
}


def _word_in_token(word: str, token: str) -> bool:
    token = (token or "").strip().upper()
    return (" " + token + " ").find(" " + word.upper() + " ") != -1


def _find_month_header_row(rows: List[List[str]]) -> int | None:
    for i, row in enumerate(rows):
        upper = [str(c or "").strip().upper() for c in row]
        found = set()
        for cell in upper:
            for key, mon in _MONTH_MAP.items():
                if _word_in_token(key, cell):
                    found.add(mon)
        if len(found) >= 2:
            return i
    return None


def _find_day_row(rows: List[List[str]], month_header_idx: int) -> int | None:
    # Look for a row with many numeric day values after the month header
    for i in range(month_header_idx + 1, min(month_header_idx + 5, len(rows))):
        row = rows[i]
        numeric_count = 0
        for cell in row:
            if isinstance(cell, (int, float)) and 1 <= cell <= 31:
                numeric_count += 1
            elif isinstance(cell, str):
                m = re.match(r"^(\d{1,2})", cell.strip())
                if m and 1 <= int(m.group(1)) <= 31:
                    numeric_count += 1
        if numeric_count >= 10:  # Should have many day numbers
            return i
    return None


def _collect_month_spans(header_row_vals: List[str]) -> List[Dict]:
    month_headers: List[Tuple[int, int]] = []
    for j, cell in enumerate(header_row_vals):
        token = (cell or "").strip().upper()
        for key, mon in _MONTH_MAP.items():
            if _word_in_token(key, token):
                month_headers.append((j, mon))
                break
    month_headers.sort(key=lambda x: x[0])
    spans: List[Dict] = []
    for idx, (col, mon) in enumerate(month_headers):
        next_col = month_headers[idx + 1][0] if idx + 1 < len(month_headers) else len(header_row_vals) + 50
        spans.append({"month": mon, "start_col": col, "end_col": max(col, next_col - 1)})
    return spans


def _normalize_section_label(boat_name: str) -> List[str]:
    up = boat_name.strip().upper()
    # known mismatch in sheet spelling
    synonyms: Dict[str, List[str]] = {
        "KANHA NATTA": ["KANHA NATHA", "KANHA NATA"],
        "KANHA LOKA": ["KANHA LOKA"],
        "KANHA CITTA": ["KANHA CITTA"],
    }
    if up in synonyms:
        return synonyms[up]
    return [up]


def _find_boat_section(rows: List[List[str]], target_labels: List[str]) -> Dict | None:
    def _norm(s: str) -> str:
        return ''.join(ch for ch in s.upper() if ch.isalpha())
    
    target_norms = [_norm(lbl) for lbl in target_labels]
    
    for i, row in enumerate(rows):
        uppers = [str(c or '').strip().upper() for c in row]
        if any(any(tn in _norm(cell) for tn in target_norms) for cell in uppers):
            # Find the end of this section (next section or blank streak)
            end_row = i + 1
            blank_streak = 0
            while end_row < len(rows):
                row = rows[end_row]
                # Check if this is another section
                head0 = (row[0] if len(row) > 0 else '').strip().upper()
                head1 = (row[1] if len(row) > 1 else '').strip().upper()
                if head0.startswith('KANHA ') or head1.startswith('KANHA '):
                    break
                
                # Check for blank lines
                is_blank = all((str(c or '').strip() == '') for c in row[:10])
                blank_streak = blank_streak + 1 if is_blank else 0
                if blank_streak >= 8:
                    break
                
                end_row += 1
            
            return {"start_row": i, "end_row": end_row - 1}
    return None


def _detect_ot_bands(rows: List[List[str]], borders: List[List[Dict]], date_row_idx: int, section_start: int, section_end: int) -> Dict:
    def is_bold(style: str | None) -> bool:
        return style in {"SOLID_MEDIUM", "SOLID_THICK", "DOUBLE"}
    
    # Find a row with many OT-like markers to serve as band row
    # Search only within the boat section boundaries
    bands_row_idx = None
    best_ot_count = 0
    
    for r_idx in range(section_start, min(section_end + 1, len(rows))):
        upper = [str(c or '').strip().upper() for c in rows[r_idx]]
        ot_count = sum(1 for c in upper if c == 'OT' or c == 'PRIVATE' or 'UPGRADE' in c)
        if ot_count >= 3:
            bands_row_idx = r_idx
            break
        elif ot_count > best_ot_count:
            best_ot_count = ot_count
            bands_row_idx = r_idx
    
    # If no row with 3+ OT markers, use the first row of the section
    if bands_row_idx is None:
        bands_row_idx = section_start
    
    # First, collect all OT marker columns
    ot_cols: List[int] = []
    for j, cell in enumerate(rows[bands_row_idx]):
        if j < len(rows[bands_row_idx]):
            token = (rows[bands_row_idx][j] or '').strip().upper()
            if token == 'OT' or token == 'PRIVATE' or 'UPGRADE' in token:
                ot_cols.append(j)
    
    # Find the CABIN/ROOM header row to use for borders
    # IMPORTANT: restrict search to the current boat section to avoid picking
    # headers from another section (e.g., Loka while parsing Natta/Citta)
    header_border_row_idx = None
    for i in range(section_start, min(section_end + 1, len(rows))):
        a = (rows[i][0] if len(rows[i]) > 0 else '').strip().upper()
        b = (rows[i][1] if len(rows[i]) > 1 else '').strip().upper()
        if 'CABIN' in a and 'ROOM' in b:
            header_border_row_idx = i
            break
    # Fallback: small window around bands_row_idx if not found inside section
    if header_border_row_idx is None:
        start_i = max(0, bands_row_idx - 5)
        end_i = min(len(rows), bands_row_idx + 6)
        for i in range(start_i, end_i):
            a = (rows[i][0] if len(rows[i]) > 0 else '').strip().upper()
            b = (rows[i][1] if len(rows[i]) > 1 else '').strip().upper()
            if 'CABIN' in a and 'ROOM' in b:
                header_border_row_idx = i
                break
    
    # Use header row for borders, fallback to OT row if not found
    border_row_idx = header_border_row_idx if header_border_row_idx is not None else bands_row_idx
    
    # For each OT column, expand to nearest bold borders to form a band
    bands: List[Tuple[int, int]] = []
    for c in ot_cols:
        # search for start: look for bold left border on current cell OR bold right border on previous cell
        start = None
        j = c
        while j >= 0:
            if (border_row_idx < len(borders) and j < len(borders[border_row_idx])):
                left_style = borders[border_row_idx][j].get("left")
                right_style = borders[border_row_idx][j].get("right")
                # Check if current cell has bold left border
                if is_bold(left_style):
                    start = j
                    break
                # Check if previous cell has bold right border
                if j > 0 and border_row_idx < len(borders) and j-1 < len(borders[border_row_idx]):
                    prev_right_style = borders[border_row_idx][j-1].get("right")
                    if is_bold(prev_right_style):
                        start = j
                        break
            j -= 1
        
        # search for end: look for bold right border on current cell OR bold left border on next cell
        end = None
        j = c
        while j < len(rows[border_row_idx]):
            if (border_row_idx < len(borders) and j < len(borders[border_row_idx])):
                left_style = borders[border_row_idx][j].get("left")
                right_style = borders[border_row_idx][j].get("right")
                # Check if current cell has bold right border
                if is_bold(right_style):
                    end = j
                    break
                # Check if next cell has bold left border
                if j + 1 < len(rows[border_row_idx]) and border_row_idx < len(borders) and j+1 < len(borders[border_row_idx]):
                    next_left_style = borders[border_row_idx][j+1].get("left")
                    if is_bold(next_left_style):
                        end = j
                        break
            j += 1
        
        if start is not None and end is not None and end >= start:
            bands.append((start, end))
    
    return {"bands": bands, "ot_row_idx": bands_row_idx}


def _col_to_date(rows: List[List[str]], day_idx: int | None, month_spans: List[Dict], col: int, default_year: int = 2025) -> str | None:
    if day_idx is None:
        return None
    month = None
    for s in month_spans:
        if s["start_col"] <= col <= s["end_col"]:
            month = s["month"]
            break
    if month is None:
        return None
    raw = rows[day_idx][col] if col < len(rows[day_idx]) else ''
    if isinstance(raw, (int, float)):
        day = int(raw)
    else:
        m = re.match(r"^(\d{1,2})", str(raw or '').strip())
        if not m:
            return None
        day = int(m.group(1))
    try:
        d = date(default_year, month, day)
        return d.isoformat()
    except Exception:
        return f"{default_year:04d}-{month:02d}-{day:02d}"


def _col_to_date_fallback(rows: List[List[str]], month_spans: List[Dict], col: int, default_year: int = 2025, search_start: int = 0, search_end: int = 10) -> str | None:
    # Search a vertical window for any row that has a day number at the given column
    month = None
    for s in month_spans:
        if s["start_col"] <= col <= s["end_col"]:
            month = s["month"]
            break
    if month is None:
        return None
    for r in range(max(0, search_start), min(len(rows), search_end + 1)):
        raw = rows[r][col] if col < len(rows[r]) else ''
        if isinstance(raw, (int, float)):
            day = int(raw)
        else:
            m = re.match(r"^(\d{1,2})", str(raw or '').strip())
            if not m:
                continue
            day = int(m.group(1))
        try:
            d = date(default_year, month, day)
            return d.isoformat()
        except Exception:
            return f"{default_year:04d}-{month:02d}-{day:02d}"
    return None


def _is_white(color: dict | None) -> bool:
    # Treat missing/None as white (default sheet background)
    if not color:
        return True
    # Check for white RGB values
    if color.get("r", 0) == 1 and color.get("g", 0) == 1 and color.get("b", 0) == 1:
        return True
    # Check for black RGB (0,0,0) - often represents transparent/no-fill cells
    if color.get("r", 0) == 0 and color.get("g", 0) == 0 and color.get("b", 0) == 0:
        return True
    # Check for indexed white (64, 65)
    indexed = color.get("indexed")
    if isinstance(indexed, int) and indexed in (64, 65):
        return True
    return False


def _get_room_link_from_sheet(worksheet, row_idx: int, col_idx: int) -> str | None:
    """Extract hyperlink from a specific cell in the worksheet"""
    try:
        service = get_sheets_service()
        spreadsheet_id = worksheet.spreadsheet.id
        
        # Get hyperlinks for the specific cell
        request = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=[f"{worksheet.title}!{chr(65 + col_idx)}{row_idx + 1}"],  # Convert to A1 notation
            includeGridData=True
        )
        response = request.execute()
        
        if 'sheets' in response and len(response['sheets']) > 0:
            sheet_data = response['sheets'][0]['data'][0]
            
            if 'rowData' in sheet_data and len(sheet_data['rowData']) > 0:
                row_data = sheet_data['rowData'][0]
                if 'values' in row_data and len(row_data['values']) > 0:
                    cell_data = row_data['values'][0]
                    if 'hyperlink' in cell_data:
                        return cell_data['hyperlink']
        
        return None
    except Exception:
        return None


def _map_sheet_room_to_config_room(sheet_room_name: str) -> str | None:
    """Map sheet room name to config room name for Kanha Loka"""
    # Normalize the sheet room name for matching
    normalized = sheet_room_name.strip().upper()
    
    # Mapping based on keywords in the room names
    if "SHARE" in normalized and "8 PAX" in normalized:
        return "Regular Sharing Cabin"
    elif "SUPERIOR" in normalized:
        return "Superior Cabin"
    elif "DELUXE" in normalized and "OCEAN VIEW" in normalized:
        return "Deluxe Cabin"
    elif "FAMILY" in normalized and "OCEAN VIEW" in normalized:
        return "Family Sharin Cabin"
    elif "MASTER" in normalized and "OCEAN VIEW" in normalized:
        return "Master"
    
    return None


def parse_kanha_from_sheets(boat_name: str) -> List[Dict]:
    from ..config import BOAT_CATALOG, get_room_link

    if boat_name not in BOAT_CATALOG:
        return []

    sheet_link = BOAT_CATALOG[boat_name].get("sheet_link")
    if not sheet_link:
        return []

    gc = get_gspread_client()
    sheet = gc.open_by_url(sheet_link)

    results: List[Dict] = []
    current_year = 2025

    # acceptable section labels we search for
    target_labels = _normalize_section_label(boat_name)

    # Find the target worksheet with pattern "Booking Chart {year}"
    target_ws = None
    target_sheet_name = f"Booking Chart {current_year}"
    for ws in sheet.worksheets():
        if ws.title == target_sheet_name:
            target_ws = ws
            break
    
    if target_ws is None:
        return []

    # Process only the target worksheet
    ws = target_ws
    rows = ws.get('A1:ZZ2000')
    service = get_sheets_service()
    colors = get_worksheet_colors(service, sheet.id, ws.title)
    borders = get_worksheet_borders(service, sheet.id, ws.title)

    # Find month header and day rows
    header_idx = _find_month_header_row(rows)
    if header_idx is None:
        return []
    
    day_idx = _find_day_row(rows, header_idx)
    month_spans = _collect_month_spans(rows[header_idx])
    if not month_spans:
        return []

    # Find boat section
    section = _find_boat_section(rows, target_labels)
    if not section:
        return []

    # Detect OT bands (limited to the boat section)
    # Use the same day_idx (date row) for all boats, but limit OT detection to boat section
    otinfo = _detect_ot_bands(rows, borders, day_idx, section["start_row"], section["end_row"])
    if not otinfo.get("bands"):
        return []

    # First, collect all room rows and group by room name
    start_row = section["start_row"] + 1
    end_row = section["end_row"]
    
    # Group rows by (room_name, cabin_number)
    # Handle multi-row cabins where cabin number might only be in first row
    room_groups: Dict[Tuple[str, int], List[int]] = {}
    current_cabin = None
    current_room = None
    
    for r in range(start_row, min(end_row + 1, len(rows))):
        row = rows[r]
        first_cell = (row[0] if len(row) > 0 else '').strip()
        room_label = (row[1] if len(row) > 1 else '').strip()

        # If this row has a cabin number, it's the start of a new cabin
        if first_cell.isdigit() and room_label:
            try:
                current_cabin = int(first_cell)
                current_room = room_label
                key = (current_room, current_cabin)
                if key not in room_groups:
                    room_groups[key] = []
                room_groups[key].append(r)
            except ValueError:
                continue
        # If this row doesn't have a cabin number, it might be a continuation of the previous cabin
        elif not first_cell.isdigit() and current_cabin is not None and current_room is not None:
            # Check if this looks like a continuation row (empty or same room type)
            if not room_label or room_label == current_room:
                key = (current_room, current_cabin)
                if key not in room_groups:
                    room_groups[key] = []
                room_groups[key].append(r)
        # If this row has a different room label, reset current cabin
        elif room_label and room_label != current_room:
            current_cabin = None
            current_room = None
    
    # Process each room group (by room label and cabin number)
    for (room_label, cabin_no), room_rows in room_groups.items():
        available_dates: List[date] = []
        
        # For each OT band, check availability at the start column
        for start_col, end_col in otinfo["bands"]:
            # Get date for this column using the standard date row
            iso_date = _col_to_date(rows, day_idx, month_spans, start_col, current_year)
            if iso_date is None:
                # fallback: search near the date row for day numbers
                iso_date = _col_to_date_fallback(rows, month_spans, start_col, current_year, day_idx - 3, day_idx + 3)
            
            if iso_date is None:
                continue
            
            # Check if room is available: ANY row in this room group is white at this column
            is_available = False
            scanned_cells = []
            for r in room_rows:
                if (r < len(colors) and start_col < len(colors[r])):
                    cell_color = colors[r][start_col]
                    is_white = _is_white(cell_color)
                    scanned_cells.append({
                        "row": r,
                        "col": start_col,
                        "is_white": is_white,
                        "color": cell_color
                    })
                    if is_white:
                        is_available = True
                        break
            
            
            if is_available:
                try:
                    parsed_date = datetime.fromisoformat(iso_date).date()
                    available_dates.append(parsed_date)
                except ValueError:
                    pass

        # Get room link: first try to extract from sheet hyperlink, then fallback to config
        room_link = _get_room_link_from_sheet(ws, room_rows[0], 1)  # Check column 2 (0-indexed as 1)
        if not room_link:
            # Try to map sheet room name to config room name
            config_room_name = _map_sheet_room_to_config_room(room_label)
            room_link = get_room_link(boat_name, config_room_name)
        
        results.append({
            "boat_name": boat_name,
            "room_name": room_label,
            "cabin_no": cabin_no,
            "occupied": [],
            "available_dates": available_dates,
            "room_link": room_link,
        })

    return results
