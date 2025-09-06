#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, date
from typing import List, Dict, Tuple, Set
from app.sheets.client import get_gspread_client, get_sheets_service
from app.sheets.color_dump import get_worksheet_colors

def _parse_calendar_date(day_str: str, month: int, year: int = 2025) -> date:
    """Parse a day string into a date object"""
    try:
        day = int(day_str.strip())
        return date(year, month, day)
    except (ValueError, TypeError):
        return None

def _is_available_color(color: dict) -> bool:
    """Check if a color indicates availability (cyan)"""
    if not color:
        return False  # No color means not available
    
    r = color.get('r', 0)  # Default to 0 if missing
    g = color.get('g', 0)  # Default to 0 if missing
    b = color.get('b', 0)  # Default to 0 if missing
    
    # Cyan color means available (r=0, g=1, b=1)
    return r == 0 and g == 1 and b == 1

def _parse_arfisyana_calendar(rows: List[List[str]], colors: List[List[dict]], boat_name: str) -> List[Dict]:
    """Parse the ARFISYANA INDAH calendar layout"""
    results = []
    available_dates = []
    
    # Month mapping
    month_map = {
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
        "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
        "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
    }
    
    # Find month headers and parse calendar sections
    current_month = None
    current_year = 2025
    
    for i, row in enumerate(rows):
        # Look for month headers first - check every row for month changes
        # Note: Don't break early as there might be multiple months in the same row
        row_months = []
        for j, cell in enumerate(row):
            cell_upper = cell.strip().upper()
            # Check if any month name is contained in the cell
            for month_name, month_num in month_map.items():
                if month_name in cell_upper:
                    row_months.append((month_name, month_num, j))
        
        # Update current month if we found one in this row
        if row_months:
            # Use the first month found in the row
            current_month = row_months[0][1]
        
        # Look for date rows (containing day numbers)
        if current_month and any(cell.strip().isdigit() and len(cell.strip()) <= 2 for cell in row):
            # This is a date row
            for j, cell in enumerate(row):
                if cell.strip().isdigit() and len(cell.strip()) <= 2:
                    day = cell.strip()
                    parsed_date = _parse_calendar_date(day, current_month, current_year)
                    
                    if parsed_date:
                        # Check if this date cell is available (cyan)
                        if i < len(colors) and j < len(colors[i]):
                            color = colors[i][j]
                            is_available = _is_available_color(color)
                            if is_available:
                                available_dates.append(parsed_date)
    
    # Create a single "All Rooms" entry with all available dates
    if available_dates:
        results.append({
            "boat_name": boat_name,
            "room_name": "All Rooms",
            "occupied": [],  # No occupied ranges for this pattern
            "room_link": None,
            "available_dates": available_dates  # Store available dates directly
        })
    
    return results

def parse_arfisyana_from_sheets(boat_name: str, worksheet_title: str = "ARFISYANA INDAH") -> List[Dict]:
    """Parse ARFISYANA INDAH data directly from Google Sheets"""
    from ..config import BOAT_CATALOG
    
    if boat_name not in BOAT_CATALOG:
        print(f"Boat {boat_name} not found in catalog")
        return []
    
    sheet_link = BOAT_CATALOG[boat_name]["sheet_link"]
    if not sheet_link:
        print(f"No sheet_link for boat {boat_name}")
        return []
    
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
        
        # Parse the calendar data
        results = _parse_arfisyana_calendar(rows, colors, boat_name)
        return results
        
    except Exception as e:
        return []

def get_arfisyana_all_sheet_start_dates(boat_name: str, worksheet_title: str = "ARFISYANA INDAH") -> Set[date]:
    """Get all sheet start dates for ARFISYANA INDAH (both occupied and available)"""
    from ..config import BOAT_CATALOG
    
    if boat_name not in BOAT_CATALOG:
        return set()
    
    sheet_link = BOAT_CATALOG[boat_name]["sheet_link"]
    if not sheet_link:
        return set()
    
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
        
        # Parse all dates from the calendar
        all_dates = set()
        
        # Month mapping
        month_map = {
            "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
            "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
            "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
        }
        
        current_month = None
        current_year = 2025
        
        for i, row in enumerate(rows):
            # Look for month headers
            for j, cell in enumerate(row):
                cell_upper = cell.strip().upper()
                # Check if any month name is contained in the cell
                for month_name, month_num in month_map.items():
                    if month_name in cell_upper:
                        current_month = month_num
                        break
            
            # Look for date rows
            if current_month and any(cell.strip().isdigit() and len(cell.strip()) <= 2 for cell in row):
                for j, cell in enumerate(row):
                    if cell.strip().isdigit() and len(cell.strip()) <= 2:
                        day = cell.strip()
                        parsed_date = _parse_calendar_date(day, current_month, current_year)
                        if parsed_date:
                            all_dates.add(parsed_date)
        
        return all_dates
        
    except Exception as e:
        return set()
