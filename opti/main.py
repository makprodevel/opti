from fastapi import FastAPI, Depends
from .auth import auth_app
from .jwt_utils import get_current_user_email


app = FastAPI()
app.mount('/auth', auth_app)

@app.get('/')
async def home(current_email: str = Depends(get_current_user_email)):
    return current_email