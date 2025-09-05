from pydantic import BaseModel, Field
from typing import Optional

class AvailabilityQuery(BaseModel):
    start: str = Field(..., description="Start date YYYY/MM/DD")
    end: str = Field(..., description="End date YYYY/MM/DD (exclusive)")

class AvailabilityResult(BaseModel):
    start: str
    boat_name: str
    boat_link: Optional[str] = None
    room_name: str
    room_link: Optional[str] = None
