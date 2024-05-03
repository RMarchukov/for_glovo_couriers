from dataclasses import dataclass
from .credentials import AccountCredentials
from .oauth import OauthData
from .profile import ProfileData
from .settings import AccountSettings
from .filter import Filter

@dataclass
class AccountData:
    credentials: AccountCredentials
    oauth: OauthData
    profile: ProfileData
    settings: AccountSettings
    filter: Filter


