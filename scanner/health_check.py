"""Cek apakah token masih valid."""
import os
import requests

def check_broker_token():
    token = os.environ.get("BROKER_API_TOKEN", "")
    if not token:
        return False, "Token kosong"
    
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
            return False, "Token expired (401)"
        else:
            return False, f"Status {r.status_code}"
    except Exception as e:
        return False, str(e)
      
