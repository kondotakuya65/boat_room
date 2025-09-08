from datetime import date
from typing import List, Dict, Set

from .client import get_gspread_client, get_sheets_service
from .color_dump import get_worksheet_colors


def _parse_calendar_date(day_str: str, month: int, year: int = 2025) -> date | None:
    """Parse a day string into a date object"""
    try:
        day = int(day_str.strip())
        return date(year, month, day)
    except Exception:
        return None


def _is_white(color: dict) -> bool:
    """Check if a color is pure white (available)"""
    if not color:
        return False
    r = color.get("r", 0)
    g = color.get("g", 0)
    b = color.get("b", 0)
    # Treat only pure white as available
    return r == 1 and g == 1 and b == 1


def _parse_calendar(rows: List[List[str]], colors: List[List[dict]], boat_name: str) -> List[Dict]:
    """
    Parse calendar-style layout for VMI boats using proper month section detection.
    
    Logic:
    1. Detect month name
    2. Detect columns of this month section by scanning next row with weekday names
    3. Detect dates cells from next rows and this columns area
    """
    results: List[Dict] = []
    available_dates: List[date] = []

    month_map = {
        # English
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
        "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
        "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
        # Indonesian variants commonly seen in sheets
        "JANUARI": 1, "FEBRUARI": 2, "MARET": 3, "APRIL": 4,
        "MEI": 5, "JUNI": 6, "JULI": 7, "AGUSTUS": 8,
        "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12,
    }
    
    current_year = 2025

    # Step 1: Find all month sections
    month_sections = []
    for i, row in enumerate(rows):
        # Look for month names in this row
        for j, cell in enumerate(row):
            cell_upper = (cell or "").strip().upper()
            for month_name, month_num in month_map.items():
                if month_name in cell_upper:
                    # Found a month header at position (i, j)
                    # Now determine the column range for this month section
                    month_start_col = j - 1
                    month_end_col = month_start_col + 6
                    
                    month_sections.append({
                        'month': month_num,
                        'month_name': month_name,
                        'start_col': month_start_col,
                        'end_col': month_end_col,
                        'header_row': i
                    })
    
    # Step 2: Parse date cells within each month section
    for section in month_sections:
        month_num = section['month']
        start_col = section['start_col']
        end_col = section['end_col']
        header_row = section['header_row']
        
        # Define the row boundaries for this month section
        # Each month section has a specific number of rows (typically 6-7 rows)
        # Start from header_row + 2 (skip header and weekday rows)
        # End at header_row + 8 (6 rows of dates)
        start_row = header_row + 2
        end_row = header_row + 8
        
        # Parse date cells within the month section's row boundaries
        for i in range(start_row, min(end_row, len(rows))):
            if i >= len(rows):
                break
                
            row = rows[i]
            
            # Check if this row contains date numbers within the month's column range
            has_dates = any((cell or "").strip().isdigit() and len((cell or "").strip()) <= 2 
                           for cell in row[start_col:end_col])
            
            if has_dates:
                # Parse date cells within this month's column range
                for j in range(start_col, min(end_col, len(row))):
                    cell_text = (row[j] or "").strip()
                    if cell_text.isdigit() and len(cell_text) <= 2:
                        parsed = _parse_calendar_date(cell_text, month_num, current_year)
                        if not parsed:
                            continue
                        # Only process dates that are actually in the target year (2025)
                        if parsed.year == current_year:
                            if i < len(colors) and j < len(colors[i]):
                                color = colors[i][j]
                                if _is_white(color):
                                    available_dates.append(parsed)

    if available_dates:
        results.append({
            "boat_name": boat_name,
            "room_name": "All Rooms",
            "occupied": [],
            "room_link": None,
            "available_dates": available_dates,
        })

    return results


def _parse_from_sheet(boat_name: str, worksheet_title: str) -> List[Dict]:
    """Parse a specific worksheet for a boat"""
    from ..config import BOAT_CATALOG
    if boat_name not in BOAT_CATALOG:
        return []
    sheet_link = BOAT_CATALOG[boat_name].get("sheet_link")
    if not sheet_link:
        return []

    gc = get_gspread_client()
    sh = gc.open_by_url(sheet_link)
    ws = sh.worksheet(worksheet_title)
    rows = ws.get_all_values()

    sheets_service = get_sheets_service()
    colors = get_worksheet_colors(sheets_service, sh.id, worksheet_title)
    return _parse_calendar(rows, colors, boat_name)


def parse_vinca_from_sheets(boat_name: str, worksheet_title: str = "PRIVATE VINCA 2025") -> List[Dict]:
    """Parse VMI Vinca boat data"""
    return _parse_from_sheet(boat_name, worksheet_title)


def parse_raffles_from_sheets(boat_name: str, worksheet_title: str = "PRIVATE RAFFLES 2025") -> List[Dict]:
    """Parse VMI Raffles boat data"""
    return _parse_from_sheet(boat_name, worksheet_title)


def get_vmi_all_sheet_start_dates(boat_name: str, worksheet_title: str) -> Set[date]:
    """Get all possible start dates from the sheet for calendar-style boats"""
    dates: Set[date] = set()
    from ..config import BOAT_CATALOG
    if boat_name not in BOAT_CATALOG:
        return dates
    sheet_link = BOAT_CATALOG[boat_name].get("sheet_link")
    if not sheet_link:
        return dates
    
    gc = get_gspread_client()
    sh = gc.open_by_url(sheet_link)
    ws = sh.worksheet(worksheet_title)
    rows = ws.get_all_values()

    month_map = {
        # English
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
        "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
        "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
        # Indonesian variants
        "JANUARI": 1, "FEBRUARI": 2, "MARET": 3, "APRIL": 4,
        "MEI": 5, "JUNI": 6, "JULI": 7, "AGUSTUS": 8,
        "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12,
    }
    
    current_year = 2025
    
    # Use the same month section detection logic as the main parser
    month_sections = []
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            cell_upper = (cell or "").strip().upper()
            for month_name, month_num in month_map.items():
                if month_name in cell_upper:
                    month_start_col = j - 1
                    month_end_col = month_start_col + 6
                    
                    month_sections.append({
                        'month': month_num,
                        'start_col': month_start_col,
                        'end_col': month_end_col,
                        'header_row': i
                    })
    
    # Extract all date numbers from each month section
    for section in month_sections:
        month_num = section['month']
        start_col = section['start_col']
        end_col = section['end_col']
        header_row = section['header_row']
        
        for i in range(header_row + 2, len(rows)):
            row = rows[i]
            for j in range(start_col, min(end_col, len(row))):
                cell_text = (row[j] or "").strip()
                if cell_text.isdigit() and len(cell_text) <= 2:
                    parsed = _parse_calendar_date(cell_text, month_num, current_year)
                    if parsed and parsed.year == current_year:
                        dates.add(parsed)
    
    return dates
