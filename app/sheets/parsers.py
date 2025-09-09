from typing import List, Dict, Callable
from .client import get_gspread_client
from .open_trip_parser import parse_open_trip_from_sheets
from .sip1_parser import parse_sip1_from_sheets
from .vmi_parser import parse_vinca_from_sheets, parse_raffles_from_sheets
from .arfisyana_parser import parse_arfisyana_from_sheets
from .barakati_parser import parse_barakati_from_sheets
from .elrora_parser import parse_elrora_from_sheets
from .kanha_parser import parse_kanha_from_sheets
from .sehat_parser import parse_sehat_from_sheets

# Each parser returns a list of room dicts: {boat_name, boat_link?, room_name, room_link, occupied: [(start,end), ...]}

Parser = Callable[[], List[Dict]]


def parser_boat_1() -> List[Dict]:
    boat_name = "LaMain Voyages I"
    return parse_open_trip_from_sheets(boat_name)


def parser_boat_2() -> List[Dict]:
    boat_name = "SIP 1"
    return parse_sip1_from_sheets(boat_name)


def parser_boat_3() -> List[Dict]:
    boat_name = "KLM Arfisyana"
    return parse_arfisyana_from_sheets(boat_name)


def parser_boat_4() -> List[Dict]:
    boat_name = "VMI Vinca"
    return parse_vinca_from_sheets(boat_name)


def parser_boat_5() -> List[Dict]:
    boat_name = "VMI Raffles"
    return parse_raffles_from_sheets(boat_name)


def parser_boat_6() -> List[Dict]:
    boat_name = "Barakati"
    return parse_barakati_from_sheets(boat_name)


def parser_boat_7() -> List[Dict]:
    boat_name = "El Rora"
    return parse_elrora_from_sheets(boat_name)


def parser_boat_8() -> List[Dict]:
    boat_name = "Sehat Elona from Lombok"
    return parse_sehat_from_sheets(boat_name)


def parser_boat_9() -> List[Dict]:
    boat_name = "Sehat Elona from Labuan Bajo"
    return parse_sehat_from_sheets(boat_name)


def parser_boat_10() -> List[Dict]:
    boat_name = "Kanha Loka"
    return parse_kanha_from_sheets(boat_name)


def parser_boat_11() -> List[Dict]:
    boat_name = "Kanha Natta"
    return parse_kanha_from_sheets(boat_name)


def parser_boat_12() -> List[Dict]:
    boat_name = "Kanha Citta"
    return parse_kanha_from_sheets(boat_name)


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
    "El Rora": parser_boat_7,
    "Sehat Elona from Lombok": parser_boat_8,
    "Sehat Elona from Labuan Bajo": parser_boat_9,
    "Kanha Loka": parser_boat_10,
    "Kanha Natta": parser_boat_11,
    "Kanha Citta": parser_boat_12,
}


def get_rooms_with_occupied_ranges_for_boat(boat_name: str) -> List[Dict]:
    parser = _BOAT_TO_PARSER.get(boat_name)
    if not parser:
        return []
    return parser()
