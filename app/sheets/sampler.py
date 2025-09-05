import os
import re
import csv
from typing import List
import gspread

from .client import get_gspread_client

_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def extract_spreadsheet_id(sheet_link: str) -> str:
    m = _SPREADSHEET_ID_RE.search(sheet_link)
    if not m:
        raise ValueError("Invalid Google Sheets link")
    return m.group(1)


def _is_hidden(ws) -> bool:
    props = getattr(ws, "_properties", {}) or {}
    return bool(props.get("hidden", False))


def download_samples_for_spreadsheet(sheet_link: str, boat_name: str) -> List[str]:
    client = get_gspread_client()
    spreadsheet_id = extract_spreadsheet_id(sheet_link)
    sh = client.open_by_key(spreadsheet_id)
    saved: List[str] = []
    dest_root = os.path.join("data", "samples", boat_name)
    _ensure_dir(dest_root)
    for ws in sh.worksheets():
        if _is_hidden(ws):
            continue
        title = ws.title
        rows = ws.get_all_values()
        dest_path = os.path.join(dest_root, f"{title}.csv")
        with open(dest_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for r in rows:
                writer.writerow(r)
        saved.append(dest_path)
    return saved
