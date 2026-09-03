import os
import json
import time
import hashlib
import requests

from ui import *
from ecdsa import SigningKey, SECP256k1
from ecdsa.util import sigencode_der

from getpass import getpass
from cryptography.exceptions import InvalidTag

from core import address_from_pubkey
from core import normalize_address
from core import validate_address
from core import checksum
from wallet import Wallet

# ====================================
# CONFIG
# ====================================

NODE = "http://127.0.0.1:5000"

Queen = 100_000_000

FEE = 1000

# ====================================
# SCAN WALLET
# ====================================

WALLET_DIR = "Wallet"

def scan_wallets():

    wallets = []

    if not os.path.exists(WALLET_DIR):
        return wallets

    for file in os.listdir(WALLET_DIR):

        if file.endswith(".json"):

            wallets.append(file[:-5])

    wallets.sort()

    return wallets

# =====================================
# FORMAT ADDRESS
# =====================================

def format_address(address):
    return address

# ====================================
# TRANSACTION
# ====================================

banner("TRANSACTION")
print()

wallets = scan_wallets()

if not wallets:

    print("❌ No Wallet Found.")
    exit()

print("Wallet found")
print()

for i, wallet in enumerate(wallets, 1):

    print(f"{i}. {wallet}")

print()

select = input("Select Wallet : ").strip()

if not select.isdigit():

    print("❌ Invalid.")
    exit()

select = int(select)

if select < 1 or select > len(wallets):

    print("❌ Wallet not found.")
    exit()

wallet_name = wallets[select - 1]

WALLET_FILE = os.path.join(
    WALLET_DIR,
    wallet_name + ".json"
)

# =========================================
# LOAD WALLET
# =========================================

with open(WALLET_FILE) as f:
    data = json.load(f)

print()
print("🔑 PIN is hidden for security.")
pin = getpass("PIN : ").strip()
print()

try:
    private_key = Wallet.decrypt_private_key(
        data,
        pin
    )

except InvalidTag:
    print("\n❌ Wrong PIN")
    exit()

except Exception:
    print("\n❌ Wallet file corrupted")
    exit()

sk = SigningKey.from_string(
    bytes.fromhex(private_key),
    curve=SECP256k1
)

public_key = sk.get_verifying_key().to_string().hex()

ADDRESS = normalize_address(
    address_from_pubkey(public_key)
)

# =========================================
# HELPERS
# =========================================

def serialize(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))

def dsha256(d):
    return hashlib.sha256(hashlib.sha256(d).digest()).hexdigest()

def compute_txid(tx):
    c = dict(tx)
    c.pop("txid", None)
    return dsha256(serialize(c).encode())

def node_get(p):
    return requests.get(NODE + p, timeout=10).json()

def node_post(p, d):
    return requests.post(NODE + p, json=d, timeout=15).json()

def get_balance():
    res = node_get(f"/balance/{ADDRESS}")
    return res["balance"]

# =========================================
# PAYLOAD
# =========================================

def payload(tx):
    base = {
        "version": tx["version"],
        "inputs": [],
        "outputs": tx["outputs"],
        "fee": tx.get("fee", 0),
        "timestamp": tx["timestamp"],
        "message": tx.get("message", "")
    }

    for i in tx["inputs"]:
        base["inputs"].append({
            "txid": i["txid"],
            "vout": i["vout"]
        })

    return serialize(base).encode()

# =========================================
# SIGN
# =========================================

def sign(tx):

    data = payload(tx)

    digest = hashlib.sha256(
        hashlib.sha256(data).digest()
    ).digest()

    sig = sk.sign_digest(
        digest,
        sigencode=sigencode_der
    ).hex()

    for i in tx["inputs"]:
        i["public_key"] = public_key
        i["signature"] = sig

    return tx

# =========================================
# GET UTXO
# =========================================

def get_utxos():
    res = node_get(f"/utxo/{ADDRESS}")
    return res.get("utxos", [])

# =========================================
# BUILD TX
# =========================================

def build(to, amount, msg):

    utxos = get_utxos()

    if not utxos:
        print("❌ no utxo")
        exit()

    needed = amount + FEE

    selected = []
    total = 0

    utxos = sorted(
        utxos,
        key=lambda x: x["amount"]
    )

    for u in utxos:

        if u.get("spent", False):
            continue

        selected.append(u)
        total += u["amount"]

        if total >= needed:
            break

    if total < needed:
        print("❌ insufficient balance")
        exit()

    change = total - needed

    if change < 0:
        print("❌ Change Error")
        exit()

    # INPUT
    inputs = []
    for u in selected:
        inputs.append({
            "txid": u["txid"],
            "vout": u["vout"]
        })

    # OUTPUT
    outputs = [{
        "address": to,
        "amount": amount
    }]

    # CHANGE
    if change > 0:
        outputs.append({
            "address": ADDRESS,
            "amount": change
        })

    # TX
    tx = {
        "version": 2,
        "inputs": inputs,
        "outputs": outputs,
        "fee": FEE,
        "timestamp": int(time.time()),
        "message": msg
    }

    # SIGN
    tx = sign(tx)
    tx["txid"] = compute_txid(tx)
    banner("TRANSACTION ID")
    print()
    p(C.W, f"TXID : {tx['txid']}")

    return tx

# ======================================
# ADDRESS BOOK
# ======================================

ADDRESS_BOOK = "AddressBook.json"

def load_addressbook():

    if not os.path.exists(ADDRESS_BOOK):

        with open(ADDRESS_BOOK, "w") as f:
            json.dump({}, f, indent=2)

    with open(ADDRESS_BOOK, "r") as f:
        return json.load(f)

def save_addressbook(book):
    print("🔑 PIN is hidden for security.")
    print()
    with open(ADDRESS_BOOK, "w") as f:
        json.dump(book, f, indent=2)

# =========================================
# MAIN
# =========================================

def main():

    banner("TRANSACTION")
    print()
    p(C.W, f"Wallet Name : {data['name']}")
    p(C.W, f"Address     : {ADDRESS}")
    utxos = get_utxos()

    if not utxos:

        print("ERROR")

        p(C.W, "❌ No Balance")
        p(C.W, "This wallet has no UTXO.")
        p(C.W, "Mine a block first.")

        return
    balance = sum(u["amount"] for u in utxos if not u.get("spent"))
    balance = get_balance()
    p(C.W, f"Balance     : {balance / Queen:.8f} QUIN")
    p(C.W, f"Timestamp   : {int(time.time())}")
    print()

    banner("SEND")
    print()
    print(f"Receiver")
    print()

    print("1. Address Book")
    print("2. New Address")
    print("3. Cancel")
    print()

    receiver = input("Select : ").strip()

    if receiver == "1":

        book = load_addressbook()

        if not book:

            print("\n❌ Address Book Empty.")
            return

        print()

        names = sorted(book.keys())

        for i, name in enumerate(names, 1):
            print(f"{i}. {name}")

        print()
        select = input("Select Receiver : ").strip()

        if not select.isdigit():

            print("\n❌ Invalid selection.")
            return

        select = int(select)

        if select < 1 or select > len(names):

            print("\n❌ Receiver not found.")
            return

        receiver_name = names[select - 1]

        to = book[receiver_name]

    elif receiver == "2":

        alias = input("Receiver Name    : ").strip()

        receiver_name = alias

        to = normalize_address(input("Receiver Address : ").strip())

        save = input("Save Address? (Y/N) : ").lower()

        if save == "y":

            book = load_addressbook()

            book[alias] = to

            save_addressbook(book)

    elif receiver == "3":

        return

    else:

        print("\n❌ Invalid selection.")
        return

    banner("AMOUNT SEND")
    print()
    print("Example")
    print()
    print("1")
    print("0.1")
    print("0.01")
    print("0.001")
    print("0.0001")
    print()
    print("Fee Network")
    print("0.00001")
    print()

    try:

        amount = int(
            float(input("Amount : ")) * Queen
        )

    except:

        banner("ERROR")

        p(C.W, "❌ Invalid Amount")
        p(C.W, "Please enter a valid number.")

        return

    print()
    print(f"Message (OPTIONAL) Max 280 characters")
    print(f"Press ENTER to skip Message...")
    print()

    msg = input("> ").strip()
    print()

    if len(msg) > 280:

        print("\n❌ Message Too Long")
        return

    needed = amount + FEE

    banner("SEND CONFIRM")
    print()
    p(C.W, f"Wallet     : {data['name']}")
    p(C.W, f"Address    : {ADDRESS}")
    p(C.Y, f"Receiver   : {receiver_name}")
    p(C.Y, f"Address    : {to}")
    p(C.W, f"Amount     : {amount / Queen:.8f} QUIN")
    p(C.W, f"Fee        : {FEE / Queen:.8f} QUIN")
    p(C.W, f"Total      : {needed / Queen:.8f} QUIN")
    p(C.W, f"Timestamp  : {int(time.time())}")

    if msg.strip():

        p(C.W, f"Message    : {msg}")

    else:

        p(C.W, "Message    : None")

    print()
    confirm = input("Confirm Send? (Y/N) : ").strip().lower()
    print()

    if confirm != "y":
        banner("TRANSACTION")
        print()
        p(C.W, f"❌Transaction Cancelled")

        return

    print()
    banner(f"🔑 Signing...")
    print()
    p(C.W, f"Timestamp : {int(time.time())}")
    time.sleep(0.6)
    tx = build(to, amount, msg)
    print()
    print(f"Broadcasting")
    time.sleep(0.5)
    print(f"Waiting Node")
    time.sleep(0.5)
    print()

    res = node_post("/transaction", tx)

    if res.get("status") == "accepted":

        banner(f"✅ Transaction Accepted")
        p(C.W, f"Node   : {NODE}")
        print()

        banner("BALANCE CHANGE")
        print()
        p(C.W, f"Address  : {ADDRESS}")
        p(C.W, f"Amount   : {amount / Queen:.8f} QUIN")
        p(C.W, f"Fee      : {FEE / Queen:.8f} QUIN")

        change = sum(
            o["amount"]
            for o in tx["outputs"]
            if o["address"] == ADDRESS
        )

        p(C.W, f"Change     : {change / Queen:.8f} QUIN")
        p(C.W, f"Timestamp  : {int(time.time())}")
        print()

    else:

       banner("TRANSACTION")
       print()

       p(C.W, "❌ Transaction Rejected")

       reason = res.get("reason", "Unknown Error")

       p(C.W, f"Reason : {reason}")

       if "txid" in tx:
           banner(f"TRANSACTION ID")
           print()
           p(C.W, f"TXID TX  : {tx['txid']}")

# =========================================
# MAIN
# =========================================

if __name__ == "__main__":
    main()
