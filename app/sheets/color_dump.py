import os
import json
from typing import Dict, Any

from .client import get_gspread_client, get_sheets_service
from .sampler import extract_spreadsheet_id


def dump_worksheet_colors(sheet_link: str, worksheet_title: str, boat_name: str) -> str:
    service = get_sheets_service()
    spreadsheet_id = extract_spreadsheet_id(sheet_link)

    # Find the sheetId for the given title
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    target_sheet_id = None
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        if props.get("title") == worksheet_title:
            target_sheet_id = props.get("sheetId")
            break
    if target_sheet_id is None:
        raise ValueError("Worksheet not found")

    rng = f"{worksheet_title}!A1:ZZ999"
    grid = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[rng],
        includeGridData=True
    ).execute()

    grid_data = grid["sheets"][0].get("data", [])
    colors = []
    for block in grid_data:
        for row in block.get("rowData", []) or []:
            row_colors = []
            for cell in row.get("values", []) or []:
                bg = (cell.get("effectiveFormat", {}) or {}).get("backgroundColor", {}) or {}
                row_colors.append({
                    "r": bg.get("red", 0),  # Default to 0 if missing
                    "g": bg.get("green", 0),  # Default to 0 if missing
                    "b": bg.get("blue", 0),  # Default to 0 if missing
                })
            colors.append(row_colors)

    dest_root = os.path.join("data", "colors", boat_name)
    os.makedirs(dest_root, exist_ok=True)
    dest_path = os.path.join(dest_root, f"{worksheet_title}.json")
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(colors, f)
    return dest_path


def get_worksheet_colors(service, spreadsheet_id: str, worksheet_title: str) -> list:
    """Get worksheet colors directly without saving to file"""
    # Find the sheetId for the given title
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    target_sheet_id = None
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        if props.get("title") == worksheet_title:
            target_sheet_id = props.get("sheetId")
            break
    if target_sheet_id is None:
        raise ValueError("Worksheet not found")

    rng = f"{worksheet_title}!A1:ZZ999"
    grid = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[rng],
        includeGridData=True
    ).execute()

    grid_data = grid["sheets"][0].get("data", [])
    colors = []
    for block in grid_data:
        for row in block.get("rowData", []) or []:
            row_colors = []
            for cell in row.get("values", []) or []:
                bg = (cell.get("effectiveFormat", {}) or {}).get("backgroundColor", {}) or {}
                row_colors.append({
                    "r": bg.get("red", 0),  # Default to 0 if missing
                    "g": bg.get("green", 0),  # Default to 0 if missing
                    "b": bg.get("blue", 0),  # Default to 0 if missing
                })
            colors.append(row_colors)

    return colors


def get_worksheet_borders(service, spreadsheet_id: str, worksheet_title: str) -> list:
    """Get worksheet cell borders. Returns 2D array with border styles per side.

    Each cell is a dict: {"left": style|None, "right": style|None, "top": style|None, "bottom": style|None}
    Styles are Google enum strings like "SOLID", "SOLID_MEDIUM", "SOLID_THICK", "DASHED", "DOUBLE", etc.
    """
    # Find the sheetId for the given title
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    target_sheet_id = None
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        if props.get("title") == worksheet_title:
            target_sheet_id = props.get("sheetId")
            break
    if target_sheet_id is None:
        raise ValueError("Worksheet not found")

    rng = f"{worksheet_title}!A1:ZZ999"
    grid = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[rng],
        includeGridData=True
    ).execute()

    grid_data = grid["sheets"][0].get("data", [])
    borders = []
    for block in grid_data:
        for row in block.get("rowData", []) or []:
            row_borders = []
            for cell in row.get("values", []) or []:
                fmt = (cell.get("effectiveFormat", {}) or {})
                br = (fmt.get("borders", {}) or {})
                row_borders.append({
                    "left": (br.get("left", {}) or {}).get("style"),
                    "right": (br.get("right", {}) or {}).get("style"),
                    "top": (br.get("top", {}) or {}).get("style"),
                    "bottom": (br.get("bottom", {}) or {}).get("style"),
                })
            borders.append(row_borders)

    return borders