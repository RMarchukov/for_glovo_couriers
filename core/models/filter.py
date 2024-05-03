from dataclasses import dataclass
from .time_diapason import TimeDiapason

@dataclass
class Filter:
    days: list
    intervals: list[TimeDiapason]
    messages_sending_1: str
    chat_id_1: str
    messages_sending_2: str
    chat_id_2: str
    zone: str
