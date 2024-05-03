from dataclasses import dataclass

@dataclass
class OauthData:
    access_token: str
    refresh_token: str