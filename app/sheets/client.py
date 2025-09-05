import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def get_gspread_client():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "api_key.json")
    credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(credentials)
