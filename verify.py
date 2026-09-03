import json
import time

from ui import *
from core import Blockchain


# ========================================
# LOAD
# ========================================

bc = Blockchain()

with open("Queen.json") as f:
    chain = json.load(f)


# ========================================
# VERIFY BLOCK
# ========================================

def verify_block(block):

    clean = dict(block)

    clean.pop("chain", None)
    clean.pop("nonce", None)

    header = bc.serialize(clean).encode()

    seed = bc.dsha256_bytes(header)

    buffer = bc.build_cpu_buffer(seed)

    result = bc.cpu_algorithm(
        buffer,
        seed,
        block["nonce"]
    )

    stored = block["chain"]

    print()
    banner("BLOCK STORED")
    print()

    print(f"Block       : {block['block']}")
    print(f"Timestamp   : {block['timestamp']}")
    print(f"Difficulty  : {block['difficulty']}")
    print(f"Merkle root : {block['merkle_root']}")
    print("Transaction  :")
    print(json.dumps(block["transactions"], indent=2))
    print(f"Prev chain  : {block['previous_chain']}")
    print(f"Nonce       : {block['nonce']}")
    print(f"Chain       : {block['chain']}")
    print()

    banner("CHAIN CHECK")
    print()
    print(f"Stored    :", stored)
    print(f"Result    :", result)
    print()

    banner("VERIFICATION")
    print()
    print(f"Waiting 3 seconds")
    print(f"Don't trust founder.")
    print(f"Verify yourself.")
    print()

    if result == stored:
        time.sleep(3)
        print("Status    : ✅ VALID")
        time.sleep(3)
        print("Match     : True")

    else:
        print("Status    : ❌ INVALID")
        print("Match     : False")

    print()


# ========================================
# MENU
# ========================================

def menu():

    while True:

        print()
        banner("QUEEN VERIFIER")
        print()

        print("1. Verify Block")
        print("2. Verify All Blocks")
        print("3. Exit")
        print()

        choice = input("Select : ").strip()

        # -------------------------------
        # VERIFY ONE
        # -------------------------------

        if choice == "1":

            print()
            print(f"Available blocks : 0 - {len(chain) - 1}")
            print()

            try:
                height = int(input("Block : ").strip())

            except ValueError:
                print("❌ Invalid block number")
                continue

            if height < 0 or height >= len(chain):
                print("❌ Block not found")
                continue

            verify_block(chain[height])

            input("Press Enter to return...")

        # -------------------------------
        # VERIFY ALL
        # -------------------------------

        elif choice == "2":

            print()

            for block in chain:

                verify_block(block)

                time.sleep(0.05)

            input("Press Enter to return...")

        # -------------------------------
        # EXIT
        # -------------------------------

        elif choice == "3":

            print()
            banner("BYE BYE")
            break

        else:

            print("❌ Invalid choice")


# ========================================
# RUN
# ========================================

if __name__ == "__main__":
    menu()
