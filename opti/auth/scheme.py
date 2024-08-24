from pydantic import BaseModel


class FetchGoogleClientId(BaseModel):
    GOOGLE_CLIENT_ID: str