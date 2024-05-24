from fastapi import FastAPI
from .auth import auth
from .user_api import user_api


app = FastAPI()
app.include_router(auth)
app.include_router(user_api)
