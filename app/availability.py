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
    filtered_out_dates = []
    duration_filtered = []
    
    for start_date in sorted(all_sheet_start_dates):
        # Only consider dates within the query range
        if start_date < request_start_date or start_date >= request_end_date:
            filtered_out_dates.append(start_date)
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
            # Calculate trip duration: find the next available start date or use request_end_date
            trip_duration = _calculate_trip_duration(start_date, all_sheet_start_dates, request_end_date)
            
            # Only include trips that are 2+ days
            if trip_duration >= 2:
                available_dates.append(start_date.strftime("%Y/%m/%d"))
            else:
                duration_filtered.append(start_date)
    
    print(f"[AVAILABILITY] Using {len(all_sheet_start_dates) - len(filtered_out_dates)}/{len(all_sheet_start_dates)} dates within range, found {len(available_dates)} available, filtered {len(duration_filtered)} by duration")
    
    return available_dates


def _calculate_trip_duration(start_date, all_sheet_start_dates: set, request_end_date) -> int:
    """Calculate trip duration in days from start_date to next available start date"""
    from datetime import timedelta
    
    # Find the next start date after this one
    next_start_date = None
    for other_date in sorted(all_sheet_start_dates):
        if other_date > start_date:
            next_start_date = other_date
            break
    
    # If no next start date found, use request_end_date
    if next_start_date is None:
        next_start_date = request_end_date
    
    # Calculate duration
    duration = (next_start_date - start_date).days
    return duration
