from __future__ import annotations

DOMAIN = "ha-aqara-devices"
PLATFORMS: list[str] = ["switch"]  # only services for this MVP

# Endpoint used for attribute write/query
REQUEST_PATH = "/app/v1.0/lumi/res/write"  # per AqaraPOST examples
QUERY_PATH = "/app/v1.0/lumi/res/query"
HISTORY_PATH = "/app/v1.0/lumi/res/history/log"
DEVICES_PATH = "/app/v1.0/lumi/app/position/device/query"

# Command
CAMERA_ACTIVE =  {"api": "set_video", "inApp": "camera_active"}
DETECT_HUMAN_ACTIVE = {"api": "humans_track_enable", "inApp": "detect_human_active"}

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