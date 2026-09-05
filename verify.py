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
    print()
    print("Transaction :")
    print(json.dumps(block["transactions"], indent=2))
    print()
    print(f"Prev chain  : {block['previous_chain']}")
    print(f"Nonce       : {block['nonce']}")
    p(C.W, f"Chain       : {block['chain']}")
    print()

    banner("CHAIN CHECK")
    print()
    print(f"Stored    :", stored)
    print()
    print(f"Nonce     : {block['nonce']}")
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
        p(C.Y, f"Status    : ✅ VALID")
        p(C.W, f"Match     : True")

    else:
        print(f"Status    : ❌ INVALID")
        print(f"Match     : False")

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

        #1
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

            input("Press ENTER to return...")

        #2
        elif choice == "2":

            print()

            for block in chain:

                verify_block(block)

                time.sleep(0.05)

            input("Press ENTER to return...")

        #3
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
