#!/usr/bin/env python3

from datetime import date, datetime
from typing import List, Dict, Tuple, Set
import re

from .client import get_gspread_client, get_sheets_service
from .color_dump import get_worksheet_colors


def _is_white(color: dict) -> bool:
    if not color:
        return False
    return color.get("r", 0) == 1 and color.get("g", 0) == 1 and color.get("b", 0) == 1


def _parse_date_range(token: str, month: int, year: int) -> Tuple[str, str] | None:
    token = (token or "").strip()
    if not token or '-' not in token:
        return None
    parts = token.replace(" ", "").split("-")
    if len(parts) != 2:
        return None
    try:
        start_day = int(parts[0])
        end_day = int(parts[1])
    except ValueError:
        return None

    start_month = month
    end_month = month
    end_year = year
    if end_day < start_day:
        if month == 12:
            end_month = 1
            end_year = year + 1
        else:
            end_month = month + 1

    start_str = f"{year:04d}/{start_month:02d}/{start_day:02d}"
    end_str = f"{end_year:04d}/{end_month:02d}/{end_day:02d}"
    return start_str, end_str


_MONTH_MAP = {
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
    # Indonesian month names
    "DESEMBER": 12, "JANUARI": 1, "FEBUARI": 2, "MARET": 3, "APRIL": 4,
    "MEI": 5, "JUNI": 6, "JULI": 7, "AGUSTUS": 8, "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11,
}


def _word_in_token(word: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", token) is not None


def _row_has_months(row: List[str]) -> bool:
    upper = [str(c or "").strip().upper() for c in row]
    found = set()
    for cell in upper:
        for key in _MONTH_MAP.keys():
            if _word_in_token(key, cell):
                found.add(_MONTH_MAP[key])
    return len(found) >= 2


def _collect_month_spans(header_row_vals: List[str], merged_ranges: List[Dict] = None) -> List[Dict]:
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
        # Default end column (next month header or end of row)
        next_month_col = month_headers[idx + 1][0] if idx + 1 < len(month_headers) else len(header_row_vals) + 50
        end_col = max(col, next_month_col - 1)
        
        # Check if this month header is part of a merged range
        if merged_ranges:
            for merge in merged_ranges:
                merge_start_row = merge.get('startRowIndex', 0)
                merge_end_row = merge.get('endRowIndex', 0)
                merge_start_col = merge.get('startColumnIndex', 0)
                merge_end_col = merge.get('endColumnIndex', 0)
                
                # Check if the month header column is within this merged range
                # We need to find the header row index to check properly
                if (merge_start_row <= 0 <= merge_end_row and  # Assuming header is around row 0
                    merge_start_col <= col < merge_end_col):
                    # This month header is part of a merged range
                    end_col = merge_end_col - 1
                    break
        
        spans.append({"month": mon, "start_col": col, "end_col": end_col})
    
    return spans


def parse_elrora_from_sheets(boat_name: str) -> List[Dict]:
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

    # Link mapping by index order from config
    config_rooms_order = list((BOAT_CATALOG[boat_name].get("rooms") or {}).keys())

    for ws in sheet.worksheets():
        rows = ws.get('A1:ZZ1000')
        service = get_sheets_service()
        colors = get_worksheet_colors(service, sheet.id, ws.title)

        # Get merged cell information from Google Sheets API v4
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
            # Fallback to heuristic method if API call fails
            pass

        i = 0
        while i < len(rows) - 2:
            # Find a month header row
            if not _row_has_months(rows[i]):
                i += 1
                continue
            header_row_idx = i
            range_row_idx = i + 1
            header_vals = rows[header_row_idx]
            range_vals = rows[range_row_idx] if range_row_idx < len(rows) else []
            month_spans = _collect_month_spans(header_vals, merged_ranges)

            # Determine next header to bound this block
            j = range_row_idx + 1
            next_header_idx = None
            while j < len(rows):
                if _row_has_months(rows[j]):
                    next_header_idx = j
                    break
                j += 1

            # Collect room rows between range_row_idx+1 and next_header_idx (or until blank streak)
            room_rows: List[Tuple[str, int]] = []
            r = range_row_idx + 1
            blank_streak = 0
            while r < len(rows) and (next_header_idx is None or r < next_header_idx):
                label = (rows[r][1] if len(rows[r]) > 1 else '').strip()
                if label:
                    room_rows.append((label, r))
                    blank_streak = 0
                else:
                    blank_streak += 1
                    if blank_streak >= 2:
                        # consider end of block
                        break
                r += 1

            # For each room row, compute available dates across all month spans/columns
            for idx_room, (label, r_idx) in enumerate(room_rows):
                # Use sheet room name; link by index position if available
                room_name = label
                room_link = None
                if idx_room < len(config_rooms_order):
                    room_link = get_room_link(boat_name, config_rooms_order[idx_room])

                available_dates: List[date] = []
                for span in month_spans:
                    mon = span["month"]
                    start_c = span["start_col"]
                    end_c = span["end_col"]
                    for col_idx in range(start_c, end_c + 1):
                        token = (range_vals[col_idx] if col_idx < len(range_vals) else '').strip()
                        if not token or '-' not in token:
                            continue
                        parsed = _parse_date_range(token, mon, current_year)
                        if not parsed:
                            continue
                        start_str, _ = parsed
                        start_dt = datetime.strptime(start_str, "%Y/%m/%d").date()
                        
                        # Check if this cell is part of a merged range that's occupied
                        is_occupied = False
                        if merged_ranges:
                            for merge in merged_ranges:
                                merge_start_row = merge.get('startRowIndex', 0)
                                merge_end_row = merge.get('endRowIndex', 0)
                                merge_start_col = merge.get('startColumnIndex', 0)
                                merge_end_col = merge.get('endColumnIndex', 0)
                                
                                # Check if this cell is within a merged range
                                if (merge_start_row <= r_idx < merge_end_row and
                                    merge_start_col <= col_idx < merge_end_col):
                                    # This cell is part of a merged range
                                    # Check if any cell in the merged range is colored (occupied)
                                    for mr in range(merge_start_row, merge_end_row):
                                        for mc in range(merge_start_col, merge_end_col):
                                            if (mr < len(colors) and mc < len(colors[mr]) and 
                                                not _is_white(colors[mr][mc])):
                                                is_occupied = True
                                                break
                                        if is_occupied:
                                            break
                                    break
                        
                        # If not part of a merged range, check individual cell
                        if not is_occupied and r_idx < len(colors) and col_idx < len(colors[r_idx]):
                            is_occupied = not _is_white(colors[r_idx][col_idx])
                        
                        # Add to available dates only if not occupied
                        if not is_occupied:
                            available_dates.append(start_dt)

                results.append({
                    "boat_name": boat_name,
                    "room_name": room_name,
                    "occupied": [],
                    "available_dates": available_dates,
                    "room_link": room_link,
                })

            # Advance to next header (or end)
            i = next_header_idx if next_header_idx is not None else r

    return results
