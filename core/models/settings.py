from dataclasses import dataclass
from .time_diapason import TimeDiapason

@dataclass
class AccountSettings:
    actions_timeout: float
    random_timeout: list[float, float]
    worktimes: list[TimeDiapason]
