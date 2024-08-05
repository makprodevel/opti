from datetime import timedelta

import aiohttp
from aiocache import cached, Cache
from jose import jwt as _jwt, JWTError, jwk
from jose.utils import base64url_decode

from opti.core.utils import utc_now
from opti.core.config import SECRET_KEY, API_ACCESS_TOKEN_EXPIRE_MINUTES, GOOGLE_CLIENT_ID, GOOGLE_CERTS_URL, \
    GOOGLE_CERTS_TTL


def create_access_token(*, data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=15)
    to_encode.update({'exp': expire})
    encoded_jwt = _jwt.encode(to_encode, SECRET_KEY, algorithm='HS256')
    return encoded_jwt


# def create_refresh_token(id):
#     expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
#     return create_access_token(data={'sub': id}, expires_delta=expires)


def create_token(id_str: str):
    access_token_expires = timedelta(minutes=API_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={'sub': id_str}, expires_delta=access_token_expires)
    return access_token


def decode_token(token):
    return _jwt.decode(token, SECRET_KEY, algorithms=['HS256'])


@cached(cache=Cache.MEMORY, ttl=GOOGLE_CERTS_TTL)
async def get_google_certificates():
    async with aiohttp.ClientSession() as session:
        async with session.get(GOOGLE_CERTS_URL) as response:
            response.raise_for_status()
            data = await response.json()
    public_keys = data["keys"]
    return public_keys


async def decode_google_token(token: str):
    unverified_header = _jwt.get_unverified_header(token)
    public_keys = await get_google_certificates()

    public_key = None
    for key in public_keys:
        if key['kid'] == unverified_header['kid']:
            public_key = key

    rsa_key = jwk.construct(public_key)
    message, encoded_sig = token.rsplit('.', 1)
    decoded_sig = base64url_decode(encoded_sig.encode('utf-8'))

    if not rsa_key.verify(message.encode("utf8"), decoded_sig):
        raise JWTError("Signature verification failed")

    payload = _jwt.decode(token, rsa_key.to_pem().decode('utf-8'), algorithms=['RS256'],
                         audience=GOOGLE_CLIENT_ID, issuer="https://accounts.google.com")
    return payload
