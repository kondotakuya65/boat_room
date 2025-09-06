from typing import List, Dict, Callable
from .client import get_gspread_client
from .open_trip_parser import parse_open_trip_from_sheets
from .sip1_parser import parse_sip1_from_sheets

# Each parser returns a list of room dicts: {boat_name, boat_link?, room_name, room_link, occupied: [(start,end), ...]}

Parser = Callable[[], List[Dict]]


def parser_boat_1() -> List[Dict]:
    # LaMain Voyages I uses OPEN TRIP layout directly from Google Sheets
    boat_name = "LaMain Voyages I"
    return parse_open_trip_from_sheets(boat_name)


def parser_boat_2() -> List[Dict]:
    # SIP 1 uses OT SIP 1 layout directly from Google Sheets
    boat_name = "SIP 1"
    return parse_sip1_from_sheets(boat_name)


def parser_boat_3() -> List[Dict]:
    return []


def parser_boat_4() -> List[Dict]:
    return []


def parser_boat_5() -> List[Dict]:
    return []


def parser_boat_6() -> List[Dict]:
    return []


def parser_boat_7() -> List[Dict]:
    return []


def parser_boat_8() -> List[Dict]:
    return []


def parser_boat_9() -> List[Dict]:
    return []


def parser_boat_10() -> List[Dict]:
    return []


def parser_boat_11() -> List[Dict]:
    return []


def parser_boat_12() -> List[Dict]:
    return []


_PARSERS: List[Parser] = [
    parser_boat_1,
    parser_boat_2,
    parser_boat_3,
    parser_boat_4,
    parser_boat_5,
    parser_boat_6,
    parser_boat_7,
    parser_boat_8,
    parser_boat_9,
    parser_boat_10,
    parser_boat_11,
    parser_boat_12,
]


def get_all_rooms_with_occupied_ranges() -> List[Dict]:
    rooms: List[Dict] = []
    for parser in _PARSERS:
        rooms.extend(parser())
    return rooms


def refresh_all():
    return True
