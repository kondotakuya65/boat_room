from datetime import datetime
from typing import List, Tuple

DateRange = Tuple[str, str]  # (start, end) in YYYY/MM/DD, end exclusive


def parse_date(date_str: str):
    return datetime.strptime(date_str, "%Y/%m/%d").date()


def ranges_overlap(request_start: str, request_end: str, booking_start: str, booking_end: str) -> bool:
    rs = parse_date(request_start)
    re = parse_date(request_end)
    bs = parse_date(booking_start)
    be = parse_date(booking_end)
    return not (re <= bs or rs >= be)


def is_free_for_range(request_start: str, request_end: str, occupied_ranges: List[DateRange]) -> bool:
    """Check if room is free for the entire requested range (legacy function)"""
    for bs, be in occupied_ranges:
        if ranges_overlap(request_start, request_end, bs, be):
            return False
    return True


def find_available_start_dates(request_start: str, request_end: str, occupied_ranges: List[DateRange], all_sheet_start_dates: set) -> List[str]:
    """Find all available start dates within the query range - only check actual start dates from sheet data"""
    request_start_date = parse_date(request_start)
    request_end_date = parse_date(request_end)
    
    # Check which of these sheet start dates are available and within query range
    available_dates = []
    for start_date in sorted(all_sheet_start_dates):
        # Only consider dates within the query range
        if start_date < request_start_date or start_date >= request_end_date:
            continue
            
        # Check if this start date is available (not occupied)
        is_available = True
        for occupied_start, occupied_end in occupied_ranges:
            occupied_start_date = parse_date(occupied_start)
            occupied_end_date = parse_date(occupied_end)
            
            # If this start date falls within any occupied range, it's not available
            if occupied_start_date <= start_date < occupied_end_date:
                is_available = False
                break
        
        if is_available:
            available_dates.append(start_date.strftime("%Y/%m/%d"))
    
    return available_dates
