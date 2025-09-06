import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import date, datetime

from .client import get_gspread_client, get_sheets_service
from .color_dump import get_worksheet_colors


def _read_csv_rows(csv_path: str) -> List[List[str]]:
    """Read CSV file and return as list of rows"""
    if not os.path.exists(csv_path):
        return []
    
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        import csv
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return rows


def _read_colors(json_path: str) -> List[List[Dict]]:
    """Read colors JSON file"""
    if not os.path.exists(json_path):
        return []
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _parse_date_range_cell(cell_value: str, month: int) -> Optional[Tuple[date, date]]:
    """Parse date range from cell value like '4-6', '7-9', etc."""
    if not cell_value or not cell_value.strip():
        return None
    
    # Clean the cell value
    cell_value = cell_value.strip()
    
    # Handle different formats
    if '-' in cell_value:
        parts = cell_value.split('-')
        if len(parts) == 2:
            try:
                start_day = int(parts[0].strip())
                end_day = int(parts[1].strip())
                
                year = 2025
                
                # Handle month overflow (e.g., "30-1" means 30th to 1st of next month)
                if end_day < start_day:
                    # Cross-month range
                    start_date = date(year, month, start_day)
                    if month == 12:
                        end_date = date(year + 1, 1, end_day)
                    else:
                        end_date = date(year, month + 1, end_day)
                else:
                    # Same month range
                    start_date = date(year, month, start_day)
                    end_date = date(year, month, end_day)
                
                return (start_date, end_date)
            except (ValueError, TypeError):
                return None
    
    return None


def _is_white(color: Optional[Dict]) -> bool:
    """Check if color is white (available)"""
    if color is None:
        return True  # No color means white/available
    r = color.get('r'); g = color.get('g'); b = color.get('b')
    return (r is None and g is None and b is None) or (r == 1 and g == 1 and b == 1)


def parse_sip1_from_sheets(boat_name: str, worksheet_title: str = "OT SIP 1 ") -> List[Dict]:
    """Parse SIP 1 data directly from Google Sheets"""
    from ..config import BOAT_CATALOG
    
    if boat_name not in BOAT_CATALOG:
        return []
    
    sheet_link = BOAT_CATALOG[boat_name]["sheet_link"]
    if not sheet_link:
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
        
        return _parse_sip1_data(rows, colors, boat_name)
        
    except Exception as e:
        print(f"Error parsing {boat_name} sheet: {e}")
        return []


def _parse_sip1_data(rows: List[List[str]], colors: List[List[Dict]], boat_name: str) -> List[Dict]:
    """Parse SIP 1 data from rows and colors arrays"""
    # The month headers are in row 10 (0-indexed: 9)
    # The date ranges are in row 11 (0-indexed: 10)
    # Room data starts from row 12 (0-indexed: 11)
    
    if len(rows) < 12:
        return []
    
    month_header_row = rows[9]   # Row 10: Month headers
    date_range_row = rows[10]    # Row 11: Date ranges
    
    # Parse month headers and map to month numbers
    month_map = {
        "APRIL": 4, "MEI": 5, "JUNI": 6, "JULI": 7, "AGUSTUS": 8,
        "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12
    }
    
    # Find month boundaries in the header row
    col_to_month: Dict[int, int] = {}
    current_month = None
    
    for c, cell_value in enumerate(month_header_row):
        cell_upper = cell_value.strip().upper()
        if cell_upper in month_map:
            current_month = month_map[cell_upper]
        if current_month:
            col_to_month[c] = current_month
    
    # Parse date ranges from row 11 with month context
    col_to_range: Dict[int, Optional[Tuple[date, date]]] = {}
    
    for c, cell_value in enumerate(date_range_row):
        month = col_to_month.get(c, 9)  # Default to September if no month found
        rng = _parse_date_range_cell(cell_value, month)
        col_to_range[c] = rng

    # Room name mapping based on the config
    room_name_map = {
        "MASTER OCEAN 1": "Master Ocean 1",
        "PRIVATE CABIN 2": "Private Cabin 2", 
        "PRIVATE CABIN 3": "Private Cabin 3",
        "PRIVATE CABIN 4": "Private Cabin 4",
        "SHARING CABIN": "Sharing Cabin 5",
    }

    # Track occupied ranges per room
    per_room: Dict[str, set] = {}

    # Process room rows (rows 12-22, 0-indexed: 11-21)
    # Each room has multiple beds, so we need to aggregate by room
    room_bed_mapping = [
        (11, 2, "MASTER OCEAN 1"),      # Row 12-13 (2 beds)
        (13, 2, "PRIVATE CABIN 2"),     # Row 14-15 (2 beds)
        (15, 2, "PRIVATE CABIN 3"),     # Row 16-17 (2 beds)
        (17, 2, "PRIVATE CABIN 4"),     # Row 18-19 (2 beds)
        (19, 4, "SHARING CABIN"),       # Row 20-23 (4 beds)
    ]
    
    for start_row, num_beds, room_label in room_bed_mapping:
        if start_row >= len(rows) or start_row >= len(colors):
            continue
            
        # Map to canonical room name
        canonical = room_name_map.get(room_label)
        if not canonical:
            continue
            
        # Initialize bucket for this room
        bucket = per_room.setdefault(canonical, set())
        
        # Check all beds for this room
        # Track occupied dates per bed, then aggregate at room level
        bed_occupied_ranges = []
        
        for bed_idx in range(num_beds):
            r_idx = start_row + bed_idx
            if r_idx >= len(rows) or r_idx >= len(colors):
                continue
                
            room_row = rows[r_idx]
            color_row = colors[r_idx]
            
            # Track occupied dates for this bed
            bed_occupied = set()
            
            # Check each column for occupied dates (starting from column 3, 0-indexed: 2)
            for c in range(2, min(len(room_row), len(color_row))):
                rng = col_to_range.get(c)
                if not rng:
                    continue
                    
                color = color_row[c] if c < len(color_row) else None
                if color is None:
                    continue
                    
                is_white_color = _is_white(color)
                if not is_white_color:  # Non-white means occupied
                    start, end = rng
                    bed_occupied.add((start.strftime("%Y/%m/%d"), end.strftime("%Y/%m/%d")))
            
            bed_occupied_ranges.append(bed_occupied)
        
        # Aggregate at room level: room is occupied only if ALL beds are occupied for that date range
        # This means a room is available if ANY bed is available
        if bed_occupied_ranges:
            # Start with all possible occupied ranges from all beds
            all_occupied = set()
            for bed_occupied in bed_occupied_ranges:
                all_occupied.update(bed_occupied)
            
            # Remove ranges where at least one bed is available
            for bed_occupied in bed_occupied_ranges:
                for occupied_range in all_occupied.copy():
                    if occupied_range not in bed_occupied:
                        # This bed is available for this range, so room is available
                        all_occupied.discard(occupied_range)
            
            # Add the remaining ranges (where all beds are occupied)
            bucket.update(all_occupied)

    # Convert to results
    results: List[Dict] = []
    for room_name, occupied_set in per_room.items():
        occupied = sorted(list(occupied_set))
        results.append({
            "boat_name": boat_name,
            "room_name": room_name,
            "occupied": occupied,
        })

    return results


def parse_sip1_from_files(boat_name: str, worksheet_title: str = "OT SIP 1 ") -> List[Dict]:
    """Parse SIP 1 data from local files (for testing/fallback)"""
    base_csv = os.path.join("data", "samples", boat_name, f"{worksheet_title}.csv")
    base_json = os.path.join("data", "colors", boat_name, f"{worksheet_title}.json")
    rows = _read_csv_rows(base_csv)
    colors = _read_colors(base_json)
    
    return _parse_sip1_data(rows, colors, boat_name)


def get_sip1_all_sheet_start_dates(boat_name: str, worksheet_title: str = "OT SIP 1 ") -> set:
    """Get all sheet start dates for SIP 1 (both occupied and available)"""
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
        
        # Parse month headers and date ranges to get all start dates
        if len(rows) < 12:
            return set()
        
        month_header_row = rows[9]   # Row 10: Month headers
        date_range_row = rows[10]    # Row 11: Date ranges
        
        # Parse month headers and map to month numbers
        month_map = {
            "APRIL": 4, "MEI": 5, "JUNI": 6, "JULI": 7, "AGUSTUS": 8,
            "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DESEMBER": 12
        }
        
        # Find month boundaries in the header row
        col_to_month = {}
        current_month = None
        
        for c, cell_value in enumerate(month_header_row):
            cell_upper = cell_value.strip().upper()
            if cell_upper in month_map:
                current_month = month_map[cell_upper]
            if current_month:
                col_to_month[c] = current_month
        
        # Parse date ranges from row 11 with month context
        all_sheet_start_dates = set()
        
        for c, cell_value in enumerate(date_range_row):
            month = col_to_month.get(c, 9)  # Default to September if no month found
            rng = _parse_date_range_cell(cell_value, month)
            if rng:
                start_date, end_date = rng
                all_sheet_start_dates.add(start_date)
        
        return all_sheet_start_dates
        
    except Exception as e:
        return set()
