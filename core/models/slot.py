from dataclasses import dataclass

@dataclass
class SlotData:
    id: int
    weekday: str
    date_ts: int
    start_ts: int
    end_ts: int
    booked: bool