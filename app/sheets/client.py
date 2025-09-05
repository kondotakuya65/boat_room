import os
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def _credentials():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "api_key.json")
    return Credentials.from_service_account_file(creds_path, scopes=SCOPES)


def get_gspread_client():
    credentials = _credentials()
    return gspread.authorize(credentials)


def get_sheets_service():
    credentials = _credentials()
    return build("sheets", "v4", credentials=credentials)
