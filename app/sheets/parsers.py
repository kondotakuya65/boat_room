from typing import List, Dict, Callable, Set
import concurrent.futures
import time
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

# Global storage for sheet start dates from parsers that provide them
_lamain_sheet_start_dates: Set = set()


def parser_boat_1() -> List[Dict]:
    boat_name = "LaMain Voyages I"
    global _lamain_sheet_start_dates
    print(f"[PARSER] Starting parser for {boat_name}")
    rooms, sheet_dates = parse_open_trip_from_sheets(boat_name)
    print(f"[PARSER] Got {len(rooms)} rooms and {len(sheet_dates)} sheet dates")
    _lamain_sheet_start_dates = sheet_dates
    print(f"[PARSER] Stored {len(_lamain_sheet_start_dates)} sheet dates globally")
    return rooms


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


# Simple in-memory caches with timestamps
_CACHE_ALL_ROOMS: Dict[str, object] = {"ts": 0.0, "data": []}
_CACHE_PER_BOAT: Dict[str, Dict[str, object]] = {}


def get_all_rooms_with_occupied_ranges() -> List[Dict]:
    # Cache results for a short TTL to reduce API calls and avoid rate limits
    ttl_seconds = 60
    now = time.time()
    if _CACHE_ALL_ROOMS["ts"] and (now - _CACHE_ALL_ROOMS["ts"]) < ttl_seconds:
        print("[PARSER] Returning cached all-rooms result")
        return _CACHE_ALL_ROOMS["data"]

    rooms: List[Dict] = []
    # Run parsers concurrently with limited parallelism and per-parser timeout
    per_parser_timeout_seconds = 25
    max_workers = min(4, len(_PARSERS))
    print(f"[PARSER] Running {len(_PARSERS)} parsers concurrently (max_workers={max_workers}) with {per_parser_timeout_seconds}s timeout each")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, parser in enumerate(_PARSERS):
            # Small stagger between submissions to smooth burstiness
            if idx > 0:
                time.sleep(0.15)
            futures.append((executor.submit(parser), parser))
        for future, parser_fn in futures:
            parser_name = getattr(parser_fn, "__name__", "unknown_parser")
            try:
                result = future.result(timeout=per_parser_timeout_seconds)
                rooms.extend(result or [])
                print(f"[PARSER] {parser_name} completed: +{len(result or [])} rooms")
            except concurrent.futures.TimeoutError:
                print(f"[PARSER] {parser_name} timed out after {per_parser_timeout_seconds}s; skipping")
            except Exception as e:
                print(f"[PARSER] {parser_name} failed: {e}")
    print(f"[PARSER] Aggregated total rooms: {len(rooms)}")
    _CACHE_ALL_ROOMS["ts"] = now
    _CACHE_ALL_ROOMS["data"] = rooms
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
    # Cache per-boat for a short TTL to reduce API calls
    ttl_seconds = 60
    now = time.time()
    cache_entry = _CACHE_PER_BOAT.get(boat_name)
    if cache_entry and (now - cache_entry["ts"]) < ttl_seconds:
        print(f"[PARSER] Returning cached result for boat {boat_name}")
        return cache_entry["data"]

    # Run the single parser with a timeout to avoid hanging requests
    per_parser_timeout_seconds = 25
    parser_name = getattr(parser, "__name__", boat_name)
    print(f"[PARSER] Running single parser {parser_name} with {per_parser_timeout_seconds}s timeout")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(parser)
        try:
            result = future.result(timeout=per_parser_timeout_seconds)
            print(f"[PARSER] {parser_name} completed: {len(result or [])} rooms")
            data = result or []
            _CACHE_PER_BOAT[boat_name] = {"ts": now, "data": data}
            return data
        except concurrent.futures.TimeoutError:
            print(f"[PARSER] {parser_name} timed out after {per_parser_timeout_seconds}s; returning empty list")
            return []
        except Exception as e:
            print(f"[PARSER] {parser_name} failed: {e}; returning empty list")
            return []


def get_lamain_sheet_start_dates() -> Set:
    """Get the sheet start dates for Lamain Voyages I (cached from last parser call)"""
    print(f"[PARSER] Retrieved {len(_lamain_sheet_start_dates)} sheet dates from global storage")
    return _lamain_sheet_start_dates
