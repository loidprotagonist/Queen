import time
import json
import copy

from core import Blockchain
from ui import *

# =========================================
# CONFIG
# =========================================

MAX_REORG = 5

# =========================================
# VALIDATE CHAIN
# =========================================

def is_valid_chain(chain_data):

    try:

        if not chain_data:
            return False

        temp_chain = Blockchain()
        temp_chain.chain = []
        temp_chain.utxos = []
        temp_chain.txblock = set()
        temp_chain.total_supply = 0
        temp_chain.difficulty = chain_data[0]["difficulty"]
        seen = set()

        # =====================================
        # GENESIS
        # =====================================

        genesis = chain_data[0]

        if genesis["block"] != 0:
            print("❌ BAD GENESIS BLOCK")
            return False

        if genesis["previous_chain"] != "0000000000000000000000000000000000000000000000000000000000000000":
            print("❌ BAD GENESIS PREV")
            return False

        clean = dict(genesis)
        clean.pop("chain", None)
        clean.pop("nonce", None)

        header = temp_chain.serialize(clean).encode()

        seed = temp_chain.dsha256_bytes(header)

        buffer = temp_chain.build_cpu_buffer(seed)

        h = temp_chain.cpu_algorithm(
            buffer,
            seed,
            genesis["nonce"]
        )

        if genesis["merkle_root"] != temp_chain.compute_merkle_root(
            genesis["transactions"]
        ):
            print("❌ BAD GENESIS MERKLE")
            return False

        if genesis["difficulty"] != temp_chain.difficulty:
            print("❌ BAD GENESIS DIFFICULTY")
            return False

        if h != genesis["chain"]:
            print("❌ BAD GENESIS CHAIN")
            return False

        temp_chain.chain.append(genesis)
        seen.add(genesis["chain"])

        # UTXO
        for tx in genesis["transactions"]:

             if "txid" not in tx:
                 tx["txid"] = temp_chain.compute_txid(tx)

        # =====================================
        # PROCESS BLOCKS
        # =====================================

        for i in range(1, len(chain_data)):

            curr = chain_data[i]

            # =====================================
            # BLOCK HEIGHT
            # =====================================

            if curr["block"] != i:
                print("❌ BAD BLOCK HEIGHT")
                return False

            # =====================================
            # TIMESTAMP
            # =====================================

            if curr["timestamp"] < chain_data[i - 1]["timestamp"]:
                print("❌ BAD TIMESTAMP")
                return False

            # =====================================
            # DUPLICATE BLOCK
            # =====================================

            if curr["chain"] in seen:
                print("❌ DUPLICATE BLOCK")
                return False

            seen.add(curr["chain"])

            # =====================================
            # BASIC
            # =====================================

            if "transactions" not in curr:
                print("❌ NO TX LIST")
                return False

            # =====================================
            # VALIDATE
            # =====================================

            valid, reason = temp_chain.validate_block(curr)

            if not valid:
                print(f"❌ BLOCK INVALID: {reason}")
                return False

            # =====================================
            # APPLY BLOCK
            # =====================================

            for tx in curr["transactions"]:
                temp_chain.apply_tx(tx, temp_chain.utxos)

            temp_chain.chain.append(curr)
            temp_chain.adjust_difficulty()

        return True

    except Exception as e:
        print("❌ CHAIN ERROR:", e)
        return False

# =========================================
# CHAIN WORK
# =========================================

def chain_work(chain_data):

    work = 0

    try:
        for block in chain_data:
            difficulty = block["difficulty"]

            if not isinstance(difficulty, int):
                return 0

            if difficulty < 0:
                return 0

            work += 2 ** difficulty

        return work

    except Exception:
        return 0

# =========================================
# RESOLVE CHAIN
# =========================================

def resolve_chain(local_chain, incoming_chain):

    try:

        if not is_valid_chain(incoming_chain):
            print("❌ REJECT INVALID CHAIN")
            return local_chain

        local_len = len(local_chain)
        incoming_len = len(incoming_chain)

        local_work = chain_work(local_chain)
        incoming_work = chain_work(incoming_chain)

        # =====================================
        # REORG LIMIT
        # =====================================

        if incoming_len - local_len > MAX_REORG:
            print("❌ REORG TOO LARGE")
            return local_chain

        # =====================================
        # MAIN RULE
        # =====================================

        if incoming_work > local_work:
            banner("✅ CHAIN REPLACED BY CUMULATIVE WORK")
            print()

            return incoming_chain

        return local_chain

    except Exception as e:
        print("❌ CONSENSUS ERROR:", e)
        return local_chain
