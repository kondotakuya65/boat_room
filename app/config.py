import csv
import json
import os
from typing import Dict

# Hard-coded catalog of boats and rooms
# Structure:
# {
#   "Boat Name": {
#       "boat_link": str | None,
#       "sheet_link": str | None,
#       "rooms": {
#           "Room Name": {"room_link": str | None}
#       }
#   },
# }

BOAT_CATALOG: Dict[str, dict] = {
    "LaMain Voyages I": {
        "boat_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/",
        "sheet_link": "https://docs.google.com/spreadsheets/d/1uA-pIPD-t5_f8IgUfB8pQ542EOVMs1U1o6Ad7lgXdm8/edit",
        "rooms": {
            "Paris": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/paris/"},
            "Osaka": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/osaka/"},
            "Athena": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/athena/"},
            "Praha": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/praha/"},
            "Venice": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/venice/"},
            "Bern": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/bern/"},
            "Bern (sharing) 1": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/bern/"},
            "Bern (sharing) 2": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/bern/"},
            "Bern (sharing) 3": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/bern/"},
            "Bern (sharing) 4": {"room_link": "https://lombok-indonesia.org/lamain-voyages-komodo-tour/bern/"},
        },
    },
    "SIP 1": {
        "boat_link": "https://lombok-indonesia.org/sip-komodo-tour/",
        "sheet_link": "https://docs.google.com/spreadsheets/d/1_x5xSDoWTH0IeJjDq-FnS4uDNyGtZLecPBwdM7XYhd8/edit",
        "rooms": {
            "Master Ocean 1": {"room_link": "https://lombok-indonesia.org/sip-komodo-tour/cabin-1/"},
            "Private Cabin 2": {"room_link": "https://lombok-indonesia.org/sip-komodo-tour/cabin-2/"},
            "Private Cabin 3": {"room_link": "https://lombok-indonesia.org/sip-komodo-tour/cabin-3/"},
            "Private Cabin 4": {"room_link": "https://lombok-indonesia.org/sip-komodo-tour/cabin-4/"},
            "Sharing Cabin 5": {"room_link": "https://lombok-indonesia.org/sip-komodo-tour/cabin-5/"},
        },
    },
    "KLM Arfisyana": {
        "boat_link": "https://lombok-indonesia.org/arfisyana-indah-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Master Room 01": {"room_link": "https://lombok-indonesia.org/arfisyana-indah-komodo-tour/master-cabin-1/"},
            "Master Room 02": {"room_link": "https://lombok-indonesia.org/arfisyana-indah-komodo-tour/master-cabin-2/"},
            "Family Room 01": {"room_link": "https://lombok-indonesia.org/arfisyana-indah-komodo-tour/sharing-cabin-1/"},
            "Family Room 02": {"room_link": "https://lombok-indonesia.org/arfisyana-indah-komodo-tour/sharing-cabin-2/"},
            "Family Room 03": {"room_link": "https://lombok-indonesia.org/arfisyana-indah-komodo-tour/sharing-cabin-3/"},
        },
    },
    "VMI Vinca": {
        "boat_link": "https://lombok-indonesia.org/vinca-voyages-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Japanese 1": {"room_link": "https://lombok-indonesia.org/vinca-voyages-komodo-tour/japanese-1/"},
            "Japanese 2": {"room_link": "https://lombok-indonesia.org/vinca-voyages-komodo-tour/japanese-2/"},
            "Western 1": {"room_link": "https://lombok-indonesia.org/vinca-voyages-komodo-tour/western-1/"},
            "Western 2": {"room_link": "https://lombok-indonesia.org/vinca-voyages-komodo-tour/western-2/"},
            "Balinese 1": {"room_link": "https://lombok-indonesia.org/vinca-voyages-komodo-tour/balinese-1/"},
            "Balinese 2": {"room_link": "https://lombok-indonesia.org/vinca-voyages-komodo-tour/balinese-2/"},
        },
    },
    "VMI Raffles": {
        "boat_link": "https://lombok-indonesia.org/raffles-cruise-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Malacca I": {"room_link": "https://lombok-indonesia.org/raffles-cruise-komodo-tour/malacca-i/"},
            "Malacca II": {"room_link": "https://lombok-indonesia.org/raffles-cruise-komodo-tour/malacca-ii/"},
            "Java": {"room_link": "https://lombok-indonesia.org/raffles-cruise-komodo-tour/java/"},
            "Borneo": {"room_link": "https://lombok-indonesia.org/raffles-cruise-komodo-tour/borneo/"},
        },
    },
    "Barakati": {
        "boat_link": "https://lombok-indonesia.org/barakati-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Wakatobi": {"room_link": "https://lombok-indonesia.org/barakati-komodo-tour/wakatobi/"},
            "Wolio": {"room_link": "https://lombok-indonesia.org/barakati-komodo-tour/wolio/"},
            "Nirwana": {"room_link": "https://lombok-indonesia.org/barakati-komodo-tour/nirwana/"},
            "Bonelalo": {"room_link": "https://lombok-indonesia.org/barakati-komodo-tour/bonelalo/"},
            "Kadatua": {"room_link": "https://lombok-indonesia.org/barakati-komodo-tour/kadatua/"},
        },
    },
    "El Rora": {
        "boat_link": "https://lombok-indonesia.org/elrora-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Love": {"room_link": "https://lombok-indonesia.org/elrora-komodo-tour/love/"},
            "Kindness": {"room_link": "https://lombok-indonesia.org/elrora-komodo-tour/kindness/"},
            "Goodness": {"room_link": "https://lombok-indonesia.org/elrora-komodo-tour/goodness/"},
            "Peace": {"room_link": "https://lombok-indonesia.org/elrora-komodo-tour/peace/"},
            "Patience": {"room_link": "https://lombok-indonesia.org/elrora-komodo-tour/patience/"},
            "Joy": {"room_link": "https://lombok-indonesia.org/elrora-komodo-tour/joy/"},
        },
    },
    "Sehat Elona from Lombok": {
        "boat_link": "https://lombok-indonesia.org/sehat-alona-labuan-bajo-lombok-komodo-tour",
        "sheet_link": "",
        "rooms": {
            "Luxury Cabin": {"room_link": "https://lombok-indonesia.org/uk/sehat-alona-labuan-bajo-lombok-komodo-tour/luxury-cabin/"},
            "Grand Deluxe": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/grand-deluxe/"},
            "Deluxe Twin": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/deluxe-twin/"},
            "Deluxe Triple": {"room_link": "https://lombok-indonesia.org/uk/sehat-alona-lombok-labuan-bajo-komodo-tour/sharing-deluxe-triple/"},
            "Regular Cabin 1": {"room_link": "https://lombok-indonesia.org/tr/sehat-alona-lombok-labuan-bajo-komodo-tour/sharing-regular-cabin-1/"},
            "Regular Cabin 2": {"room_link": "https://lombok-indonesia.org/uk/sehat-alona-lombok-labuan-bajo-komodo-tour/sharing-regular-cabin-2/"},
        },
    },
    "Sehat Elona from Labuan Bajo": {
        "boat_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour",
        "sheet_link": "",
        "rooms": {
            "Luxury Cabin": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/luxury-cabin"},
            "Grand Deluxe": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/grand-deluxe"},
            "Deluxe Twin": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/deluxe-twin"},
            "Deluxe Triple": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/sharing-deluxe-triple"},
            "Regular Cabin 1": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/sharing-regular-cabin-1"},
            "Regular Cabin 2": {"room_link": "https://lombok-indonesia.org/sehat-alona-lombok-labuan-bajo-komodo-tour/sharing-regular-cabin-2"},
        },
    },
    "Kanha Loka": {
        "boat_link": "https://lombok-indonesia.org/kanha-loka-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Master": {"room_link": "https://lombok-indonesia.org/kanha-loka-komodo-tour/master/"},
            "Deluxe Cabin": {"room_link": "https://lombok-indonesia.org/kanha-loka-komodo-tour/deluxe/"},
            "Superior Cabin": {"room_link": "https://lombok-indonesia.org/kanha-loka-komodo-tour/superior/"},
            "Family Sharin Cabin": {"room_link": "https://lombok-indonesia.org/kanha-loka-komodo-tour/family/"},
            "Regular Sharing Cabin": {"room_link": "https://lombok-indonesia.org/kanha-loka-komodo-tour/regular-sharing-cabin/"},
        },
    },
    "Kanha Natta": {
        "boat_link": "https://lombok-indonesia.org/kanha-natha-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Master Room 1": {"room_link": "https://lombok-indonesia.org/kanha-natha-komodo-tour/master-1/"},
            "Master Room 2": {"room_link": "https://lombok-indonesia.org/kanha-natha-komodo-tour/master-2/"},
            "Sharing Room 1": {"room_link": "https://lombok-indonesia.org/kanha-natha-komodo-tour/sharing-1/"},
            "Sharing Room 2": {"room_link": "https://lombok-indonesia.org/kanha-natha-komodo-tour/sharing-2/"},
        },
    },
    "Kanha Citta": {
        "boat_link": "https://lombok-indonesia.org/kanha-citta-komodo-tour/",
        "sheet_link": "",
        "rooms": {
            "Gayatri": {"room_link": "https://lombok-indonesia.org/kanha-citta-komodo-tour/gayatri/"},
            "Shakti": {"room_link": "https://lombok-indonesia.org/kanha-citta-komodo-tour/shakti/"},
            "Sedana": {"room_link": "https://lombok-indonesia.org/kanha-citta-komodo-tour/sedana/"},
            "Deluxe Room": {"room_link": "https://lombok-indonesia.org/kanha-citta-komodo-tour/deluxe-main-deck/"},
            "Sharing Room": {"room_link": "https://lombok-indonesia.org/kanha-citta-komodo-tour/sharing-cabin/"},
        },
    },
}


def get_boat_link(boat_name: str) -> str | None:
    boat = BOAT_CATALOG.get(boat_name)
    return boat.get("boat_link") if boat else None


def get_room_link(boat_name: str, room_name: str) -> str | None:
    boat = BOAT_CATALOG.get(boat_name) or {}
    room = (boat.get("rooms") or {}).get(room_name)
    return room.get("room_link") if room else None
