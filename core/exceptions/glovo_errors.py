class GlovoError(Exception):
    def __init__(self, message):
        self.message = message

class SlotTakeError(Exception):
    def __init__(self, message):
        self.message = message

class AccessTokenError(Exception):
    def __init__(self, message):
        self.message = message

class InvalidCredentials(Exception):
    def __init__(self, message):
        self.message = message

class AccountBlocked(Exception):
    def __init__(self, message):
        self.message = message