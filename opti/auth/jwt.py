from datetime import timedelta
from jose import jwt as _jwt, JWTError, jwk
from jose.utils import base64url_decode

from opti.core.utils import utc_now
from opti.core.config import SECRET_KEY, API_ACCESS_TOKEN_EXPIRE_MINUTES, GOOGLE_CLIENT_ID


def create_access_token(*, data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=15)
    to_encode.update({'exp': expire})
    encoded_jwt = _jwt.encode(to_encode, SECRET_KEY, algorithm='HS256')
    return encoded_jwt


# def create_refresh_token(email):
#     expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
#     return create_access_token(data={'sub': email}, expires_delta=expires)


def create_token(email):
    access_token_expires = timedelta(minutes=API_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={'sub': email}, expires_delta=access_token_expires)
    return access_token


def decode_token(token):
    return _jwt.decode(token, SECRET_KEY, algorithms=['HS256'])


def decode_google_token(token: str):
    unverified_header = _jwt.get_unverified_header(token)

    public_keys = [{
      "kid": "0e345fd7e4a97271dffa991f5a893cd16b8e0827",
      "e": "AQAB",
      "n": "rv95jmy91hibD7cb_BCA25jv5HrX7WoqHv-fh8wrOR5aYcM8Kvsc3mbzs2w1vCUlMRv7NdEGVBEnOZ6tHvUzGLon4ythd5XsX-wTvAtIHPkyHdo5zGpTgATO9CEn78Y-f1E8By63ttv14kXe_RMjt5aKttK4yqqUyzWUexSs7pET2zWiigd0_bGhJGYYEJlEk_JsOBFvloIBaycMfDjK--kgqnlRA8SWUkP3pEJIAo9oHzmvX6uXZTEJK10a1YNj0JVR4wZY3k60NaUX-KCroreU85iYgnecyxSdL-trpKdkg0-2OYks-_2Isymu7jPX-uKVyi-zKyaok3N64mERRQ",
      "use": "sig",
      "kty": "RSA",
      "alg": "RS256"
    },
    {
      "use": "sig",
      "kid": "f2e11986282de93f27b264fd2a4de192993dcb8c",
      "n": "zaUomGGU1qSBxBHOQRk5fF7rOVVzG5syHhJYociRyyvvMOM6Yx_n7QFrwKxW1Gv-YKPDsvs-ksSN5YsozOTb9Y2HlPsOXrnZHQTQIdjWcfUz-TLDknAdJsK3A0xZvq5ud7ElIrXPFS9UvUrXDbIv5ruv0w4pvkDrp_Xdhw32wakR5z0zmjilOHeEJ73JFoChOaVxoRfpXkFGON5ZTfiCoO9o0piPROLBKUtIg_uzMGzB6znWU8Yfv3UlGjS-ixApSltsXZHLZfat1sUvKmgT03eXV8EmNuMccrhLl5AvqKT6E5UsTheSB0veepQgX8XCEex-P3LCklisnen3UKOtLw",
      "alg": "RS256",
      "e": "AQAB",
      "kty": "RSA"
    },
    {
      "n": "nzGsrziOYrMVYMpvUZOwkKNiPWcOPTYRYlDSdRW4UpAHdWPbPlyqaaphYhoMB5DXrVxI3bdvm7DOlo-sHNnulmAFQa-7TsQMxrZCvVdAbyXGID9DZYEqf8mkCV1Ohv7WY5lDUqlybIk1OSHdK7-1et0QS8nn-5LojGg8FK4ssLf3mV1APpujl27D1bDhyRb1MGumXYElwlUms7F9p9OcSp5pTevXCLmXs9MJJk4o9E1zzPpQ9Ko0lH9l_UqFpA7vwQhnw0nbh73rXOX2TUDCUqL4ThKU5Z9Pd-eZCEOatKe0mJTpQ00XGACBME_6ojCdfNIJr84Y_IpGKvkAEksn9w",
      "kid": "87bbe0815b064e6d449cac999f0e50e72a3e4374",
      "e": "AQAB",
      "kty": "RSA",
      "use": "sig",
      "alg": "RS256"
    }]
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