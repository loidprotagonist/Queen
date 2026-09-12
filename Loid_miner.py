import time
import hashlib
import json
import requests
import multiprocessing
multiprocessing.freeze_support()

from Loid_ui import *
from Loid_core import get_blockchain
from Loid_core import normalize_address
from Loid_core import validate_address
from Loid_core import checksum
from Loid_core import check_pow
from Loid_core import get_target

# =========================================
# CONFIG
# =========================================

blockchain = get_blockchain()

NODE_URL = "http://127.0.0.1:5000"

Loid = 100_000_000

MAX_TX_PER_BLOCK = 2_000_000

FEE = 1000

# =========================================
# NODE
# =========================================

def node_get(path):
    return requests.get(NODE_URL + path, timeout=10).json()

# ==========================================
# POST
# ==========================================

def node_post(path, data):
    r = requests.post(NODE_URL + path, json=data, timeout=15)

    try:
        return r.json()
    except:
        print("\n❌ NODE ERROR RESPONSE:")
        print(r.text)
        return {"status": "error"}

# ========================================
# WORKER
# ========================================

def mine_worker(args):

    buffer, seed, difficulty, start_nonce, step, stop, result = args

    nonce = start_nonce
    hashes = 0

    while not stop.is_set():

        h = blockchain.Loid_algorithm(
            buffer,
            seed,
            nonce
        )

        hashes += 1

        if hashes % 100 == 0:
            result["nonce"] = nonce
            result["hash"] = h
            result["hashes"] = result.get("hashes", 0) + 100

        if check_pow(h, difficulty):

            if not stop.is_set():

                result["nonce"] = nonce
                result["hash"] = h
                result["hashes"] = hashes

                stop.set()

            return

        nonce += step

# =========================================
# BUILD BLOCK
# =========================================

def build_block(miner):

    info = node_get("/info")

    chain_data = node_get("/chain")

    mempool_data = node_get("/mempool")

    chain = chain_data["chain"]

    mempool = mempool_data["mempool"]

    difficulty = info["difficulty"]

    reward = info["reward"]

    last_block = chain[-1]

    height = last_block["block"] + 1

    # =====================================
    # FILTER TX
    # =====================================

    valid_txs = []
    seen = set()

    for tx in mempool:

        txid = tx.get("txid")

        if not txid or txid in seen:
            continue

        seen.add(txid)
        valid_txs.append(tx)

        if len(valid_txs) >= MAX_TX_PER_BLOCK:
            break

    total_fee = sum(tx.get("fee", 0) for tx in valid_txs)

    # =====================================
    # COINBASE
    # =====================================

    coinbase = {
        "version": 1,
        "inputs": [],
        "outputs": [
            {
                "address": miner,
                "amount": reward + total_fee
            }
        ],
        "timestamp": int(time.time()),
        "message": "MINING REWARD"
    }

    coinbase["txid"] = blockchain.compute_txid(coinbase)

    txs = [coinbase] + valid_txs

    # =====================================
    # BLOCK
    # =====================================

    block = {
        "block": height,
        "timestamp": int(time.time()),
        "difficulty": difficulty,
        "merkle_root": "",
        "transactions": txs,
        "previous_chain": last_block["chain"],
        "nonce": 0
    }

    block["merkle_root"] = blockchain.compute_merkle_root( block["transactions"])

    return block, difficulty, reward

# =========================================
# MINING
# =========================================

def mine_once(miner):

    try:
        block, difficulty, reward = build_block(miner)

        version = blockchain.chain_version
        start_height = block["block"]
        start_previous_chain = block["previous_chain"]

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(e)
        return

    height = block["block"]

    banner("INFO")
    print()
    p(C.K, f"Block      : {height}")
    p(C.K, f"Difficulty : {difficulty}")
    p(C.K, f"Timestamp  : {int(time.time())}")
    target = get_target(difficulty)
    p(C.W, f"Miner      : {miner}")
    p(C.K, f"Target     : {target:064x}")
    print()

    start = time.time()
    last_print = time.time()
    hashes = 0

    clean = dict(block)
    clean.pop("chain", None)
    clean.pop("nonce", None)

    header = blockchain.serialize(clean).encode()

    seed = blockchain.dsha256_bytes(header)

    buffer = blockchain.build_cpu_buffer(seed)

    workers = multiprocessing.cpu_count()

    manager = multiprocessing.Manager()

    stop = manager.Event()
    result = manager.dict()
    result["hashes"] = 0

    jobs = []

    for i in range(workers):

        jobs.append(
            (
                buffer,
                seed,
                difficulty,
                i,
                workers,
                stop,
                result
            )
        )


    processes = []

    for job in jobs:

        proc = multiprocessing.Process(
               target=mine_worker,
               args=(job,)
        )

        proc.start()
        processes.append(proc)


    while not stop.is_set():

        time.sleep(0.5)

        elapsed = time.time() - start

        h = result.get("hash", "")
        nonce = result.get("nonce", 0)

        total_hashes = result.get("hashes", 0)
        hps = total_hashes / elapsed if elapsed else 0
        print()
        print(
            f"\r\033[K"
            f"\r{C.K}⛏ MINING #{height}{C.X} "
            f"{C.K} NONCE {nonce:}"
            f" {hps:.2f} H/s "
            f"{C.K} HASH {h[:40]}...{C.X}",
            end="",
            flush=True
        )

        try:
            current = node_get("/chain")
            current_chain = current.get("chain", [])

            if not current_chain:
                stop.set()
                print("\n❌ Chain unavailable")
                return

            latest = current_chain[-1]

            if (
                latest["block"] != start_height - 1
                or latest["chain"] != start_previous_chain
            ):
                print()
                banner("STALE BLOCK")
                stop.set()
                return

        except Exception as e:
            print(f"\n❌ Chain check failed: {e}")
            stop.set()
            return

    print()
    time.sleep(0.5)

    for proc in processes:
        proc.terminate()

    block["nonce"] = result["nonce"]
    block["chain"] = result["hash"]

    hashes = result.get("hashes", 0)

    total_time = time.time() - start

    banner("BLOCK FOUND ⛏")
    print()
    p(C.K, f"Block         : {height}")
    p(C.K, f"Chain         : {block['chain'][:40]}....")
    p(C.K, f"Timestamp     : {int(time.time())}")
    p(C.K, f"Nonce         : {nonce}")
    p(C.W, f"Miner         : {miner}")
    p(C.K, f"Mining Time   : {total_time:.2f} Seconds")
    p(C.Y, f"Mining Reward : {reward / Loid:.8f} QUEEN")
    fee = 0

    for tx in block["transactions"]:
        if tx["inputs"]:
           fee += FEE

    p(C.Y, f"Fee Reward    : {fee / Loid:.8f} QUEEN")
    print()

    result = node_post("/submit_block", block)

    if result.get("status") == "accepted":
       banner("NETWORK STATUS")
       print()

       print(f"Broadcast...")
       time.sleep(0.5)
       print()
       print(f"Block Accepted")
       time.sleep(0.8)
       print()

    else:
        banner("NETWORK STATUS")

        p(C.K, "❌ Block Rejected")

        reason = result.get("reason", "Unknown")

        p(C.K, f"Reason : {reason}")

        p(C.K, f"Block  : {block['block']}")

# =========================================
# MAIN CONTROL
# =========================================

def main():

    banner("MINER ADDRESS")
    print()

    miner = normalize_address(input("Miner Address : "))

    if not validate_address(miner):
        p(C.K, "❌ Invalid Address")
        return

    while True:

        print()

        banner("MINER MAIN")
        print()
        p(C.K, f"1. Mine 1 Block")
        p(C.K, f"2. Mine 2 Block")
        p(C.K, f"3. Mine 5 Block")
        p(C.K, f"4. Mine 10 Block")
        p(C.K, f"5. Mine 1M Block")
        p(C.K, f"6. Miner Info")
        p(C.K, f"7. Exit")
        print()
        banner("SELECT NUMBER")
        print()
        choice = input("SELECT: ").strip()
        print()

        #1
        if choice == "1":
            mine_once(miner)

        #2
        elif choice == "2":
            for _ in range(2):
                mine_once(miner)

        #3
        elif choice == "3":
            for _ in range(5):
                mine_once(miner)
        #4
        elif choice == "4":
            for _ in range(10):
                mine_once(miner)

        #5
        elif choice == "5":
            for _ in range(1000000):
                mine_once(miner)

        #6
        elif choice == "6":

            info = node_get("/info")

            banner("MINER INFORMATION")
            print()
            p(C.W, f"Miner       : {miner}")
            p(C.K, f"Difficulty  : {info['difficulty']}")
            p(C.K, f"Timestamp   : {int(time.time())}")
            p(C.Y, f"Reward      : {info['reward'] / Loid:.8f} QUEEN")
            p(C.K, f"Algorithm   : Loid Algorithm")
            p(C.K, f"Message     : Don't Trust. Verify.")
            print()

            input("\nPress ENTER to return...")

        #7
        elif choice == "7":

             banner("BYE BYE")
             break

        else:
            p(C.W, "❌ Invalid Menu")

# =============================================
# RUN
# =============================================

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()


