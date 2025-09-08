from typing import List, Dict, Callable
from .client import get_gspread_client
from .open_trip_parser import parse_open_trip_from_sheets
from .sip1_parser import parse_sip1_from_sheets
from .vmi_parser import parse_vinca_from_sheets, parse_raffles_from_sheets
from .arfisyana_parser import parse_arfisyana_from_sheets
from .barakati_parser import parse_barakati_from_sheets

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
    # KLM Arfisyana uses ARFISYANA INDAH calendar layout directly from Google Sheets
    boat_name = "KLM Arfisyana"
    return parse_arfisyana_from_sheets(boat_name)


def parser_boat_4() -> List[Dict]:
    # VMI Vinca uses PRIVATE VINCA 2025 calendar layout
    boat_name = "VMI Vinca"
    return parse_vinca_from_sheets(boat_name)


def parser_boat_5() -> List[Dict]:
    # VMI Raffles uses PRIVATE RAFFLES 2025 calendar layout
    boat_name = "VMI Raffles"
    return parse_raffles_from_sheets(boat_name)


def parser_boat_6() -> List[Dict]:
    # Barakati uses table layout with month columns and date ranges row; white means available
    boat_name = "Barakati"
    return parse_barakati_from_sheets(boat_name)


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


# Map boat names to their specific parser functions for targeted parsing
_BOAT_TO_PARSER: dict[str, Parser] = {
    "LaMain Voyages I": parser_boat_1,
    "SIP 1": parser_boat_2,
    "KLM Arfisyana": parser_boat_3,
    "VMI Vinca": parser_boat_4,
    "VMI Raffles": parser_boat_5,
    "Barakati": parser_boat_6,
}


def get_rooms_with_occupied_ranges_for_boat(boat_name: str) -> List[Dict]:
    parser = _BOAT_TO_PARSER.get(boat_name)
    if not parser:
        return []
    return parser()
