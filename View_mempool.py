import os
import sys
import time
import requests

from Loid_ui import *

# CONFIG
TIMEOUT = 10
BASE_UNITS = 100_000_000
CURRENCY = "QUEEN"
NODE_URL = "http://127.0.0.1:5000"


# URL
def normalize_url(url):
    url = url.strip().rstrip("/")

    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    return url


# AMOUNT
def format_amount(amount):
    try:
        return f"{int(amount) / BASE_UNITS:.8f} {CURRENCY}"
    except (TypeError, ValueError):
        return str(amount)


# MEMPOOL
def get_mempool(node_url):
    response = requests.get(
        f"{node_url}/mempool",
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("Invalid mempool response")

    mempool = data.get("mempool", [])

    if not isinstance(mempool, list):
        raise ValueError("Invalid mempool list")

    return data


# VIEW TRANSACTION
def show_transaction(tx):
    banner("TRASACTION")
    print()

    print(f"TXID      : {tx.get('txid', '-')}")
    print(f"VERSION   : {tx.get('version', '-')}")
    print(f"FEE       : {format_amount(tx.get('fee', 0))}")
    print(f"TIMESTAMP : {tx.get('timestamp', '-')}")
    print()

    inputs = tx.get("inputs", [])
    outputs = tx.get("outputs", [])

    # INPUTS
    if inputs:
        for i, item in enumerate(inputs):
            p(C.Y,f"INPUT #{i}")
            print(f"TXID : {item.get('txid', '-')}")
            print(f"VOUT : {item.get('vout', '-')}")
            print()
            p(C.Y,f"PUBLIC KEY")
            print(f"{item.get('public_key', '-')}")
            print()
            p(C.Y,f"SIGNATURE")
            print(f"{item.get('signature', '-')}")
            print()

    # OUTPUTS
    if outputs:
        for i, item in enumerate(outputs):
            p(C.Y,f"OUTPUT #{i}")
            print(f"ADDRESS : {item.get('address', '-')}")
            print(f"AMOUNT  : {format_amount(item.get('amount', 0))}")
            print()

    # MESSAGE
    message = tx.get("message")

    if message:
        p(C.Y,f"MESSAGE")
        print(f"{message}")
        print()


# VIEW MEMPOOL
def show_mempool(node_url):
    try:
        data = get_mempool(node_url)

    except requests.RequestException as e:
        print(f"\n❌ Node error: {e}")
        return

    except ValueError as e:
        print(f"\n❌ Invalid response: {e}")
        return

    count = data.get(
        "count",
        len(data.get("mempool", []))
    )

    mempool = data.get("mempool", [])

    print(f"NODE     : {node_url}")
    print(f"MEMPOOL  : {count} transaction(s)")
    print()

    if not mempool:
        print("Mempool is empty.")
        return

    for tx in mempool:
        show_transaction(tx)


# REFRESH
def refresh(node_url):
    try:
        while True:
            os.system("clear")

            banner("QUEEN MEMPOOL")
            print()

            show_mempool(node_url)

            print("Refreshing every 5 seconds...")
            print("Press CTRL+C to stop.")
            print()

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\nRefresh stopped.")
        print()


# MAIN
def main():
    node_url = NODE_URL

    # Optional remote node:
    # python Loid_mempool.py https://example.pinggy.link
    if len(sys.argv) > 1:
        node_url = normalize_url(sys.argv[1])

    banner("MEMPOOL")
    print()
    print(f"NODE : {node_url}")
    print()

    while True:
        banner("MENU")
        print()

        print("1. View Mempool")
        print("2. Refresh")
        print("3. Exit")

        choice = input("\nChoice : ").strip()
        print()

        if choice == "1":
            show_mempool(node_url)

        elif choice == "2":
            refresh(node_url)

        elif choice == "3":
            banner("BYE BYE")
            break

        else:
            print("❌ Invalid choice.")


if __name__ == "__main__":
    main()
