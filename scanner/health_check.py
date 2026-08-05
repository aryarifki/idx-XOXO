"""Cek apakah token broker ada (bukan cek validitas ke API)."""
import os

def check_broker_token():
    token = os.environ.get("BROKER_API_TOKEN", "")
    if not token:
        return False, "BROKER_API_TOKEN kosong di GitHub Secrets"
    return True, "OK"
    
