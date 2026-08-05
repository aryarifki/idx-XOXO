"""Entry point health check."""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from scanner.health_check import check_broker_token
from scanner.telegram_bot import send_message

def main():
    ok, msg = check_broker_token()
    if ok:
        send_message("Health Check OK\n\nToken valid. Pipeline siap.")
        print("OK")
    else:
        send_message("Health Check FAIL\n\n" + msg)
        print("FAIL:", msg)

if __name__ == "__main__":
    main()
