import hashlib
import base64
import json
import time
import os
import requests

from ui import *
from ecdsa import (
    SigningKey,
    SECP256k1
)

from getpass import getpass
from core import address_from_pubkey
from core import normalize_address
from core import validate_address
from core import checksum

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# =========================================
# CONFIG
# =========================================

NODE = "http://127.0.0.1:5000"

Queen = 100_000_000

FEE = 1000

# =========================================
# DIRECTORY
# =========================================

WALLET_DIR = "Wallet"

if not os.path.exists(WALLET_DIR):
    os.makedirs(WALLET_DIR)

BACKUP_DIR = "Backup"

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# =========================================
# FORMAT ADDRESS
# =========================================

def format_address(address):
    return address

# =========================================
# WALLET
# =========================================

class Wallet:

    def __init__(self, private_key=None, name="Main Wallet"):

        # =================================
        # KEYS
        # =================================

        if private_key:
            self.sk = SigningKey.from_string(
                bytes.fromhex(private_key),
                curve=SECP256k1
            )
        else:
            self.sk = SigningKey.generate(curve=SECP256k1)

        self.vk = self.sk.get_verifying_key()

        self.public_key = self.vk.to_string().hex()

        self.address = self.generate_address()
        self.name = name
        self.created = int(time.time())

    # =====================================
    # KEYS
    # =====================================

    def encrypt_private_key(self, pin):

        salt = os.urandom(16)

        key = hashlib.pbkdf2_hmac(
            "sha256",
            pin.encode(),
            salt,
            300000,
            dklen=32
        )

        aes = AESGCM(key)

        nonce = os.urandom(12)

        ciphertext = aes.encrypt(
            nonce,
            self.sk.to_string(),
            None
        )

        return {
           "encrypted_private_key": base64.b64encode(ciphertext).decode(),
           "salt": base64.b64encode(salt).decode(),
           "nonce": base64.b64encode(nonce).decode()
        }

    # ====================================
    # KEYS
    # =====================================

    @staticmethod
    def decrypt_private_key(data, pin):

        salt = base64.b64decode(data["salt"])
        nonce = base64.b64decode(data["nonce"])
        ciphertext = base64.b64decode(data["encrypted_private_key"])

        key = hashlib.pbkdf2_hmac(
           "sha256",
           pin.encode(),
           salt,
           300000,
           dklen=32
        )

        aes = AESGCM(key)

        plain = aes.decrypt(
            nonce,
            ciphertext,
            None
        )

        return plain.hex()

    # =====================================
    # ADDRESS
    # =====================================

    def generate_address(self):
        return address_from_pubkey(self.public_key)

    # =====================================
    # SAVE WALLET
    # =====================================

    def save(self, filename, encrypted_key):

        data = self.export(encrypted_key)

        path = os.path.join(WALLET_DIR, filename)

        tmp = path + ".tmp"

        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)

        os.replace(tmp, path)

        return filename

    # =====================================
    # LOAD WALLET
    # =====================================

    @staticmethod
    def load(filename="wallet.json"):

        path = os.path.join(WALLET_DIR, filename)

        with open(path, "r") as f:
            data = json.load(f)

        if data.get("version") != 2:
            raise Exception("Unsupported wallet version")

        print()
        print("🔑 PIN is hidden for security.")

        pin = getpass("PIN : ").strip()

        if len(pin) < 6 or not pin.isdigit():
            raise Exception("Invalid PIN")

        try:

             private_key = Wallet.decrypt_private_key(data,pin)

             w = Wallet(private_key=private_key,name=data.get("name", "Main Wallet"))

             if normalize_address(w.address) != normalize_address(data["address"]):
                 raise Exception("Wallet corrupted")

             if w.public_key != data["public_key"]:
                 raise Exception("Wallet corrupted")

             w.created = data.get("created", int(time.time()))

             del private_key

             return w

        except InvalidTag:
            raise Exception("Wrong PIN")

        except Exception:
            raise Exception("Wallet corrupted")

    # =====================================
    # EXPORT
    # =====================================

    def export(self, encrypted_key):

        return {

            "version": 2,
            "name": self.name,
            "created": self.created,

            "address": self.address,
            "public_key": self.public_key,

            "encrypted_private_key": encrypted_key["encrypted_private_key"],
            "salt": encrypted_key["salt"],
            "nonce": encrypted_key["nonce"]
       }

# ======================================
# BALANCE
# ======================================

def get_balance(address):
    try:
        r = requests.get(f"{NODE}/balance/{address}", timeout=5)
        return r.json()["balance"]
    except:
        return 0

# ======================================
# SCAN WALLET
# ======================================

def scan_wallets():

    wallets = []

    if not os.path.exists(WALLET_DIR):
        return wallets

    for file in os.listdir(WALLET_DIR):

        if file.endswith(".json"):

            wallets.append(file[:-5])

    wallets.sort()

    return wallets

# ========================================
# SCAN BACKUP
# ========================================

def scan_backups():

    backups = []

    if not os.path.exists(BACKUP_DIR):
        return backups

    for file in os.listdir(BACKUP_DIR):

        if file.endswith(".json"):

            backups.append(file[:-5])

    backups.sort()

    return backups

# =========================================
# RUN
# =========================================

if __name__ == "__main__":

    while True:

        banner("WELCOME")
        print()
        p(C.K, "1. Create Wallet")
        p(C.K, "2. Open Wallet")
        p(C.K, "3. Send QUIN")
        p(C.K, "4. Receive QUIN")
        p(C.K, "5. Import Wallet")
        p(C.K, "6. Backup Wallet")
        p(C.K, "7. Exit")
        print()

        choice = input("Select : ").strip()
        print()

        #1
        if choice == "1":
            banner("CREATE WALLET")
            print()

            name = input("Wallet Name : ").strip()
            print()

            if not name:
                name = "Main Wallet"

            banner("PIN MINIMUM 6 DIGITS")
            print()
            print("🔑 PIN is hidden for security.")
            pin = getpass("Create PIN  : ").strip()
            confirm = getpass("Confirm PIN : ").strip()

            if pin != confirm:
                print("\n❌ PIN does not match.")
                continue

            if len(pin) < 6 or not pin.isdigit():
                print("\n❌ PIN must be at least 6 digits.")
                continue

            print()
            banner("WARNING")
            print()
            p(C.K, "Your WALLET is protected by a PIN.")
            print()
            p(C.K, "Not Your PIN.")
            p(C.K, "Not Your COIN.")
            print()

            agree = input("Create Wallet ? (Y/N) : ").lower()

            if agree != "y":

                print("\n❌ Wallet creation cancelled.")
                input("\nPress ENTER to return...")
                continue

            w = Wallet(name=name)

            encrypted = w.encrypt_private_key(pin)

            print()
            banner("WALLET")
            print()
            p(C.K, f"Wallet Name : {w.name}")
            p(C.W, f"Address     : {format_address(w.address)}")
            p(C.K, f"PIN         : ••••••")
            p(C.Y, f"Balance     : 0.00000000 QUIN")
            p(C.K, f"Timestamp   : {int(time.time())}")
            print()
            banner("Have A Nice Day")

            save = input("\nSave Wallet ? (Y/N) : ").lower()

            if save == "y":

                filename = f"{w.name}.json"

                path = os.path.join(WALLET_DIR, filename)

                if os.path.exists(path):

                    print("\n❌ Wallet already exists.")
                    input("\nPress ENTER to return...")
                    continue

                w.save(filename, encrypted)
                print()
                p(C.W, f"Saving...")
                time.sleep(0.5)
                p(C.K, f"✅ Wallet Saved")
                p(C.K, f"Location : Wallet/{filename}")
                p(C.K, f"KEEP YOUR PIN SAFE")

            else:
                print("\n❌ Wallet was not saved.")

        #2
        elif choice == "2":
            print()

            wallets = scan_wallets()

            if not wallets:

                print("\n❌ No wallet found.")
                input("\nPress ENTER to return...")
                continue

            banner("WALLET FOUND")
            print()

            for i, wallet in enumerate(wallets, 1):
                print(f"{i}. {wallet}")

            print()
            select = input("Select Wallet : ").strip()

            if not select.isdigit():

                print("\n❌ Invalid selection.")
                input("\nPress ENTER to return...")
                continue

            select = int(select)

            if select < 1 or select > len(wallets):

               print("\n❌ Wallet not found.")
               input("\nPress ENTER to return...")
               continue

            name = wallets[select - 1]

            filename = f"{name}.json"

            try:
                w = Wallet.load(filename)

            except Exception as e:
                print(f"\n❌ {e}")
                input("\nPress ENTER to return...")
                continue

            print()
            banner("WALLET")
            print()
            p(C.K, f"Wallet Name : {w.name}")
            p(C.W, f"Address     : {format_address(w.address)}")
            balance = get_balance(w.address)
            p(C.Y, f"Balance     : {balance / Queen:.8f} QUIN")
            p(C.K, f"Timestamp   : {int(time.time())}")
            print()
            banner("Have A Nice Day")

            input("\nPress ENTER to return...")

        #3
        elif choice == "3":

            os.system("python transaction.py")

        #4
        elif choice == "4":

            print()

            wallets = scan_wallets()

            if not wallets:

                print("\n❌ No wallet found.")
                input("\nPress ENTER to return...")
                continue

            print()
            banner("WALLET FOUND")

            for i, wallet in enumerate(wallets, 1):
                print(f"{i}. {wallet}")

            print()
            select = input("Select Wallet : ").strip()

            if not select.isdigit():

                print("\n❌ Invalid selection.")
                input("\nPress ENTER to return...")
                continue

            select = int(select)

            if select < 1 or select > len(wallets):

               print("\n❌ Wallet not found.")
               input("\nPress ENTER to return...")
               continue

            name = wallets[select - 1]

            filename = f"{name}.json"

            w = Wallet.load(filename)

            banner("RECEIVE")
            print()
            p(C.K, f"Wallet    : {w.name}")
            p(C.W, f"Address   : {format_address(w.address)}")
            p(C.K, f"Timestamp : { int(time.time())}")
            print()
            input("\nPress ENTER to return...")

        #5
        elif choice == "5":

            banner("IMPORT WALLET")
            print()

            backups = scan_backups()

            if not backups:

                print("\n❌ No Backup Found.")
                print("Copy your wallet backup into Backup/")
                input("\nPress ENTER to return...")
                continue

            banner("BACKUP FOUND:")
            print()

            for i, backup in enumerate(backups, 1):

                print(f"{i}. {backup}")

            print()
            select = input("Select Backup : ").strip()

            if not select.isdigit():

                print("\n❌ Invalid selection.")
                input("\nPress ENTER to return...")
                continue

            select = int(select)

            if select < 1 or select > len(backups):

               print("\n❌ Backup not found.")
               input("\nPress ENTER to return...")
               continue

            try:

                filename = backups[select - 1] + ".json"

                source = os.path.join(
                    BACKUP_DIR,
                    filename
                )

                destination = os.path.join(
                    WALLET_DIR,
                    filename
                )

                with open(source, "r") as f:
                    data = json.load(f)

                required = [
                    "version",
                    "name",
                    "address",
                    "public_key",
                    "encrypted_private_key",
                    "salt",
                    "nonce"
                ]

                for field in required:
                    if field not in data:
                       raise Exception("Invalid wallet file")

                if data["version"] != 2:
                    raise Exception("Unsupported wallet")

                if os.path.exists(destination):
                    print("\n❌ Backup already exists.")
                    input("\nPress ENTER to return...")
                    continue

                tmp = destination + ".tmp"

                with open(tmp,"w") as f:
                    json.dump(data,f,indent=2)

                os.replace(tmp,destination)

                print()
                banner("WALLET IMPORTED")
                print()
                p(C.K, f"Wallet     : {data['name']}")
                p(C.K, f"Saved      : {destination}")
                p(C.K, f"Timestamp  : {int(time.time())}")
                print()

            except Exception as e:

                print(f"\n❌ Import Failed : {e}")

                input("\nPress ENTER to return...")

        #6
        elif choice == "6":

            banner("BACKUP WALLET")
            print()

            wallets = scan_wallets()

            if not wallets:

                print("\n❌ No Wallet Found.")
                input("\nPress ENTER to return...")
                continue

            banner("WALLET FOUND")
            print()

            for i, wallet in enumerate(wallets, 1):

                print(f"{i}. {wallet}")

            print()
            select = input("Select Wallet : ").strip()

            if not select.isdigit():

                print("\n❌ Invalid selection.")
                input("\nPress ENTER to return...")
                continue

            select = int(select)

            if select < 1 or select > len(wallets):

               print("\n❌ Wallet not found.")
               input("\nPress ENTER to return...")
               continue

            filename = wallets[select - 1] + ".json"

            source = os.path.join(
                WALLET_DIR,
                filename
            )

            destination = os.path.join(
                BACKUP_DIR,
                filename
            )

            print()

            p(C.W, "Create Backup?")
            confirm = input("(Y/N) : ").lower()

            if confirm != "y":

                print("\n❌ Backup cancelled.")
                input("\nPress ENTER to return...")
                continue

            try:

                with open(source, "r") as f:
                    data = json.load(f)

                tmp = destination + ".tmp"

                with open(tmp, "w") as f:
                    json.dump(data, f, indent=2)

                os.replace(tmp, destination)

                print()
                banner("BACKUP COMPLETE")
                print()
                p(C.K, f"Wallet    : {data['name']}")
                p(C.K, f"Saved     : {destination}")
                p(C.K, f"Timestamp : {int(time.time())}")
                print()

            except Exception as e:

                print(f"\n❌ Backup Failed : {e}")

                input("\nPress ENTER to return...")

        #7
        elif choice == "7":

            banner("BYE BYE")
            break



