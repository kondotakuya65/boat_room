import pendulum
from typing import List, Tuple

DateRange = Tuple[str, str]  # (start, end) in YYYY/MM/DD, end exclusive


def parse_date(date_str: str):
    return pendulum.from_format(date_str, "YYYY/MM/DD").date()


def ranges_overlap(request_start: str, request_end: str, booking_start: str, booking_end: str) -> bool:
    rs = parse_date(request_start)
    re = parse_date(request_end)
    bs = parse_date(booking_start)
    be = parse_date(booking_end)
    return not (re <= bs or rs >= be)


def is_free_for_range(request_start: str, request_end: str, occupied_ranges: List[DateRange]) -> bool:
    for bs, be in occupied_ranges:
        if ranges_overlap(request_start, request_end, bs, be):
            return False
    return True
