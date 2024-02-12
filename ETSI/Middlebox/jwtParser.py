import os
import pickle
import sys
import time
import pathlib
from dateutil import parser
import jwt
import requests

oidc_server = "accounts.google.com"
jwks_file = "jwks.dat"
jwks_info_file = "jwks_info.dat"


def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


reload_jwks = True
if os.path.isfile(jwks_file) and os.path.isfile(jwks_info_file):
    try:
        (signing_algos, expiration) = pickle.load(open(jwks_info_file, "rb"))
        if expiration > time.time():
            reload_jwks = False
    except pickle.UnpicklingError:
        pass
if reload_jwks:
    log("Reloading jwks")
    oidc_config = requests.get(f"https://{oidc_server}/.well-known/openid-configuration").json()
    signing_algos = oidc_config["id_token_signing_alg_values_supported"]
    jwks_uri = oidc_config["jwks_uri"]
    r = requests.get(jwks_uri)
    expires = parser.parse(r.headers.get("expires")).timestamp()
    with open(jwks_file, "wb") as f:
        f.write(r.content)
    pickle.dump((signing_algos, expires), open(jwks_info_file, "wb"))

jwks_uri = pathlib.Path(os.path.abspath(jwks_file)).as_uri()
jwks_client = jwt.PyJWKClient(jwks_uri)


def parse_jwt(id_token: str) -> dict:
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    data = jwt.api_jwt.decode(
        id_token,
        key=signing_key.key,
        algorithms=signing_algos,
        issuer="https://accounts.google.com",
        options={"verify_aud": False}
    )
    return data
