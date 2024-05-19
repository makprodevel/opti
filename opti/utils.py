from functools import partial
from datetime import datetime, timezone


utc_now = partial(datetime.now, timezone.utc)