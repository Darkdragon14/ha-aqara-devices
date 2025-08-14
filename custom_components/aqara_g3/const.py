from __future__ import annotations

DOMAIN = "aqara_g3"
PLATFORMS: list[str] = []  # only services for this MVP

# Endpoint used for attribute write/query
REQUEST_PATH = "/app/v1.0/lumi/res/write"  # per AqaraPOST examples
QUERY_PATH = "/app/v1.0/lumi/res/query"

# Minimal area map (extend later as needed)
AREAS = {
    "EU": {"server": "https://rpc-ger.aqara.com", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
    "US": {"server": "https://aiot-rpc-usa.aqara.com", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
    "CN": {"server": "https://aiot-rpc.aqara.cn", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
    "OTHER": {"server": "https://aiot-rpc-usa.aqara.com", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
}

# Public key used to encrypt MD5(password) (same as token generator script)
AQARA_RSA_PUBKEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCG46slB57013JJs4Vvj5cVyMpR
9b+B2F+YJU6qhBEYbiEmIdWpFPpOuBikDs2FcPS19MiWq1IrmxJtkICGurqImRUt
4lP688IWlEmqHfSxSRf2+aH0cH8VWZ2OaZn5DWSIHIPBF2kxM71q8stmoYiV0oZs
rZzBHsMuBwA4LQdxBwIDAQAB
-----END PUBLIC KEY-----
"""