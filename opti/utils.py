from functools import partial
from datetime import datetime, timezone


utc_now = partial(datetime.now, timezone.utc)


def create_nickname_from_email(email: str) -> str:
    default_nickname = email.strip('@')[0]
    return default_nickname
