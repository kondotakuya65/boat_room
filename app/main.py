from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List
import os

from .models import AvailabilityQuery, AvailabilityResult
from .routes import router as api_router

# Get subpath from environment variable or default to empty string
SUBPATH = os.getenv("SUBPATH", "/myapp")

app = FastAPI(title="Boat Room Availability", root_path=SUBPATH)

# Mount static files with subpath
app.mount(f"{SUBPATH}/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "subpath": SUBPATH})

# API routes
app.include_router(api_router)
