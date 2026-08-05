"""Cek apakah token broker masih valid."""
import os
import requests


def check_broker_token():
    token = os.environ.get("BROKER_API_TOKEN", "")
    if not token:
        return False, "BROKER_API_TOKEN kosong"
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(
            "https://exodus.stockbit.com/marketdetectors/BBCI",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return True, "OK"
        elif r.status_code == 401:
            return False, "Token expired (401) — refresh di GitHub Secrets"
        else:
            return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)
