from dataclasses import dataclass


class AuthError(Exception):
    def __init__(self, code: str, status: int = 401):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True)
class AuthPolicy:
    access_minutes: int = 5
    refresh_days: int = 7
    reset_minutes: int = 20
