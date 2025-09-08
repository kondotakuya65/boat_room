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
    """Parse the ARFISYANA INDAH calendar layout using proper month section detection"""
    results = []
    available_dates = []
    
    # Month mapping
    month_map = {
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
        "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
        "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
    }
    
    current_year = 2025

    # Step 1: Find all month sections
    month_sections = []
    for i, row in enumerate(rows):
        # Look for month names in this row
        for j, cell in enumerate(row):
            cell_upper = cell.strip().upper()
            for month_name, month_num in month_map.items():
                if month_name in cell_upper:
                    # Found a month header at position (i, j)
                    # Simple column area detection based on header position
                    if j <= 3:  # First month in the row (B-H)
                        month_start_col = 1  # Column B (index 1)
                        month_end_col = 8    # Column H (index 7, so range is 1-7)
                    else:  # Second month in the row (J-P)
                        month_start_col = 9   # Column J (index 9)
                        month_end_col = 16    # Column P (index 15, so range is 9-15)
                    
                    month_sections.append({
                        'month': month_num,
                        'month_name': month_name,
                        'start_col': month_start_col,
                        'end_col': month_end_col,
                        'header_row': i
                    })
    
    # Step 2: Parse date cells within each month section with proper row boundaries
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
        
        # Parse date cells within the month section's row and column boundaries
        for i in range(start_row, min(end_row, len(rows))):
            if i >= len(rows):
                break
                
            row = rows[i]
            
            # Parse date cells within this month's column range
            for j in range(start_col, min(end_col, len(row))):
                cell_text = (row[j] or "").strip()
                if cell_text.isdigit() and len(cell_text) <= 2:
                    parsed_date = _parse_calendar_date(cell_text, month_num, current_year)
                    if not parsed_date:
                        continue
                    # Only process dates that are actually in the target year (2025)
                    if parsed_date.year == current_year:
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
        
        # Get all values from the worksheet with explicit range to get all columns
        # The worksheet has 26 columns but get_all_values() only returns 16
        rows = worksheet.get('A1:Z1000')  # Get columns A-Z to ensure we get all data
        
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
        
        # Get all values from the worksheet with explicit range to get all columns
        # The worksheet has 26 columns but get_all_values() only returns 16
        rows = worksheet.get('A1:Z1000')  # Get columns A-Z to ensure we get all data
        
        # Get colors using the sheets service
        sheets_service = get_sheets_service()
        colors = get_worksheet_colors(sheets_service, sheet.id, worksheet_title)
        
        # Parse all dates from the calendar using proper month section detection
        all_dates = set()
        
        # Month mapping
        month_map = {
            "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
            "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
            "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
        }
        
        current_year = 2025

        # Step 1: Find all month sections
        month_sections = []
        for i, row in enumerate(rows):
            # Look for month names in this row
            for j, cell in enumerate(row):
                cell_upper = cell.strip().upper()
                for month_name, month_num in month_map.items():
                    if month_name in cell_upper:
                        # Found a month header at position (i, j)
                        # Simple column area detection based on header position
                        if j <= 3:  # First month in the row (B-H)
                            month_start_col = 1  # Column B (index 1)
                            month_end_col = 8    # Column H (index 7, so range is 1-7)
                        else:  # Second month in the row (J-P)
                            month_start_col = 9   # Column J (index 9)
                            month_end_col = 16    # Column P (index 15, so range is 9-15)
                        
                        month_sections.append({
                            'month': month_num,
                            'start_col': month_start_col,
                            'end_col': month_end_col,
                            'header_row': i
                        })
        
        # Step 2: Extract all date numbers from each month section
        for section in month_sections:
            month_num = section['month']
            start_col = section['start_col']
            end_col = section['end_col']
            header_row = section['header_row']
            
            # Define the row boundaries for this month section
            start_row = header_row + 2
            end_row = header_row + 8
            
            for i in range(start_row, min(end_row, len(rows))):
                if i >= len(rows):
                    break
                    
                row = rows[i]
                for j in range(start_col, min(end_col, len(row))):
                    cell_text = (row[j] or "").strip()
                    if cell_text.isdigit() and len(cell_text) <= 2:
                        parsed_date = _parse_calendar_date(cell_text, month_num, current_year)
                        if parsed_date and parsed_date.year == current_year:
                            all_dates.add(parsed_date)
        
        return all_dates
        
    except Exception as e:
        return set()
