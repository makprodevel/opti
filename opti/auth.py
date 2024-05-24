import requests
from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2AuthorizationCodeBearer

from .jwt_utils import create_token, CREDENTIALS_EXCEPTION, valid_email_from_db


oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://accounts.google.com/o/oauth2/v2/auth",
    tokenUrl="https://oauth2.googleapis.com/token",
    scopes={
        "openid": "OpenID connect to authenticate users",
        "https://www.googleapis.com/auth/userinfo.email": "Access to user's email address",
        "https://www.googleapis.com/auth/userinfo.profile": "Access to user's profile information",
    },
)


auth = APIRouter(
    prefix='/auth',
    tags=['auth']
)


@auth.get('/get-token')
async def get_token(
    response: Response,
    token: str = Depends(oauth2_scheme),
):
    user_info = requests.get('https://www.googleapis.com/oauth2/v3/userinfo', headers={'Authorization': f'Bearer {token}'})
    email = user_info.json().get('email')
    if await valid_email_from_db(email):
        return response.set_cookie('jwt', create_token(email), secure=True, httponly=True)

    raise CREDENTIALS_EXCEPTION