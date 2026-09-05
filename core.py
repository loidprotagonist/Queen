import hashlib
import json
import os
import time
import threading
import multiprocessing
import copy

from ecdsa import VerifyingKey, SECP256k1
from ecdsa.util import sigdecode_der
from ui import *

# =========================================
# CONFIG
# =========================================

Queen = 100_000_000

MAX_SUPPLY = 23_000_000 * Queen

INITIAL_REWARD = int(50 * Queen)

HALVING_INTERVAL = 230_000

CHAIN_FILE = "Queen.json"

INITIAL_DIFFICULTY = 1

MAX_TARGET = int("00000" + "f" * 59, 16)

TARGET_BLOCK_TIME = 60

MAX_BLOCK_TIME = 300

ADDRESS_PREFIX = "QUEEN"

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

MAX_FUTURE_TIME = 7200

MAX_PAST_DRIFT = 7200

DIFFICULTY_ADJUST_INTERVAL = 230000

MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 2

MAX_BLOCK_SIZE = 2_000_000

VERSION = 2

COINBASE_MESSAGE = "BLOCK REWARD"

GENESIS_MESSAGE = "The Lever 13/Jan/2026 The Federal Reserve’s $420 Billion Wall Street Bailout"

BLOCK1_MESSAGE = "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks"

MAX_TX_MESSAGE_LENGTH = 280

# =====================================
# FORMAT ADDRESS
# =====================================

def format_address(address):
    return address

# =======================================
# NORMALIZE
# =======================================

def normalize_address(address):
    if not isinstance(address, str):
        return ""

    return address.strip()

# =======================================
# BASE 58
# ======================================

def base58_encode(data):
    n = int.from_bytes(data, "big")

    result = ""

    while n > 0:
        n, r = divmod(n, 58)
        result = BASE58_ALPHABET[r] + result

    pad = 0

    for b in data:
        if b == 0:
            pad += 1
        else:
            break

    return "1" * pad + result

# ========================================
# CHECK
# ========================================

def base58_decode(s):
    n = 0

    for c in s:
        n *= 58
        n += BASE58_ALPHABET.index(c)

    full = n.to_bytes((n.bit_length() + 7) // 8, "big")

    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break

    return b"\x00" * pad + full

# ========================================
# CHECKSUM
# =======================================

def checksum(data):

    return hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]

# =======================================
# VALIDATE ADDRESS
# =======================================

def validate_address(address):

    if not isinstance(address, str):
        return False

    address = normalize_address(address)

    if not address.startswith(ADDRESS_PREFIX):
        return False

    try:
        payload = base58_decode(address[len(ADDRESS_PREFIX):])

    except Exception:
        return False

    if len(payload) != 24:
        return False

    ripe = payload[:-4]
    check = payload[-4:]

    return check == checksum(ripe)

# =======================================
# ADDRESS
# =======================================

def address_from_pubkey(pubkey):

    pubkey_bytes = bytes.fromhex(pubkey)

    sha = hashlib.sha256(pubkey_bytes).digest()

    ripe = hashlib.new("ripemd160", sha).digest()

    payload = ripe + checksum(ripe)

    return ADDRESS_PREFIX + base58_encode(payload)

# =========================================
# CPU ALGORITHM
# =========================================

CPU_BUFFER_SIZE = 2 * 256 * 256
CPU_ROUNDS = 2

# =====================================
# TARGET
# =====================================

def get_target(difficulty):

    return MAX_TARGET >> difficulty

# =====================================
# CHECK POW
# =====================================

def check_pow(block_hash, difficulty):

    target = get_target(difficulty)

    return int(block_hash, 16) <= target

# =========================================
# MINING WORKER
# =========================================

def mine_worker(args):

    cpu_algorithm, buffer, seed, difficulty, start_nonce, step, result = args

    nonce = start_nonce
    count = 0

    while not result["found"]:

        h = cpu_algorithm(
            buffer,
            seed,
            nonce
        )

        count += 1

        if check_pow(h, difficulty):

            if not result["found"]:

                result["nonce"] = nonce
                result["hash"] = h
                result["count"] = count
                result["found"] = True

            return

        nonce += step

# =========================================
# BLOCKCHAIN
# =========================================

class Blockchain:

    def __init__(self):

        self.chain = []
        self.utxos = []
        self.mempool = []
        self.txindex = set()
        self.lock = threading.Lock()

        self.chain_version = 0
        self.difficulty = INITIAL_DIFFICULTY
        self.total_supply = MAX_SUPPLY
        self.max_block_size = MAX_BLOCK_SIZE
        self.target_block_time = TARGET_BLOCK_TIME
        self.max_block_time = MAX_BLOCK_TIME

        self.load_chain()
        self.rebuild_utxo()

    # =====================================
    # JSON
    # =====================================

    def serialize(self, obj):
        return json.dumps(obj, sort_keys=True, separators=(",", ":"))

    # =====================================
    # HASH
    # =====================================

    def dsha256(self, data):
        return hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()

    # =====================================
    # D HASH
    # =====================================

    def dsha256_bytes(self, data):
        return hashlib.sha256(hashlib.sha256(data).digest()).digest()

    # =====================================
    # BUILD CPU BUFFER
    # =====================================

    def build_cpu_buffer(self, seed):

        buffer = bytearray(CPU_BUFFER_SIZE)

        current = seed

        for i in range(0, CPU_BUFFER_SIZE, 32):

            current = self.dsha256_bytes(current)

            buffer[i:i+32] = current

        return buffer

    # =====================================
    # CPU ALGORITHM
    # =====================================

    def cpu_algorithm(self,buffer,seed, nonce):

        buffer = bytearray(buffer)

        current = seed

        nonce_bytes = nonce.to_bytes(
            8,
            "little"
        )

        for r in range(CPU_ROUNDS):

            pos_hash = self.dsha256_bytes(
                current + nonce_bytes
            )

            pos = int.from_bytes(
                pos_hash[:4],
                "little"
            )

            pos %= (CPU_BUFFER_SIZE - 32)

            chunk = bytes(
                buffer[pos:pos+32]
            )

            current = self.dsha256_bytes(
                current +
                chunk +
                nonce_bytes
            )

            buffer[pos:pos+32] = current

        final = current

        return self.dsha256(final)

    # =====================================
    # TXID
    # =====================================

    def compute_txid(self, tx):
        clean = dict(tx)
        clean.pop("txid", None)
        return self.dsha256(self.serialize(clean).encode())

    # =====================================
    # MERKLE ROOT
    # =====================================

    def compute_merkle_root(self, transactions):

        if not transactions:
            return self.dsha256(b"")

        level = []

        for tx in transactions:

            if "txid" not in tx:
                tx["txid"] = self.compute_txid(tx)

            level.append(tx["txid"])

        while len(level) > 1:

            if len(level) % 2 == 1:
                level.append(level[-1])

            new_level = []

            for i in range(0, len(level), 2):

                data = bytes.fromhex(level[i]) + bytes.fromhex(level[i + 1])

                new_level.append(self.dsha256(data).lower())

            level = new_level

        return level[0]

    # =====================================
    # LOAD
    # =====================================

    def load_chain(self):

        if os.path.exists(CHAIN_FILE):

            with open(CHAIN_FILE, "r") as f:
                self.chain = json.load(f)

            banner("VERIFYING BLOCKCHAIN")
            time.sleep(0.5)

            ok, reason = self.verify_chain()

            if not ok:
                raise Exception(f"Invalid blockchain: {reason}")

            if len(self.chain) == 0:

                banner("CREATE GENESIS")

                self.create_genesis()

                self.save_chain()

        else:

           print(f"CREATE GENESIS")

           self.create_genesis()

           self.save_chain()

    # =======================================
    # SAVE
    # =======================================

    def save_chain(self):

        fields = [
            "block",
            "timestamp",
            "difficulty",
            "merkle_root",
            "transactions",
            "previous_chain",
            "nonce",
            "chain"
        ]

        ordered_chain = []

        for block in self.chain:
            ordered_chain.append({
                key: block[key]
                for key in fields
                if key in block
            })

        with open(CHAIN_FILE, "w") as f:
            json.dump(ordered_chain, f, indent=2)

    # =======================================
    # VERIFY
    # =======================================

    def verify_chain(self):

        old_difficulty = self.difficulty

        self.utxos = []

        for i, block in enumerate(self.chain):

            if i == 0:
                self.difficulty = block["difficulty"]

            valid, reason = self.validate_block(block, i)

            if not valid:
                self.difficulty = old_difficulty
                return False, reason

            for tx in block["transactions"]:
                 self.apply_tx(tx, self.utxos)

            if i >= DIFFICULTY_ADJUST_INTERVAL - 1:

                 first = self.chain[i + 1 - DIFFICULTY_ADJUST_INTERVAL]

                 last = block

                 actual = last["timestamp"] - first["timestamp"]

                 expected = (DIFFICULTY_ADJUST_INTERVAL * TARGET_BLOCK_TIME)

                 if actual < expected:
                     self.difficulty += 1

                 elif actual > expected:
                     self.difficulty = max(MIN_DIFFICULTY,self.difficulty - 1)

        return True, "ok"

    # =====================================
    # GENESIS
    # =====================================

    def create_genesis(self):

        coinbase = {
            "version": 1,
            "inputs": [],
            "outputs": [{
                "address": "QUEENLPB8CiwNv4sNbaisVdMFXMjMfx6Xjy1vP",
                "amount": INITIAL_REWARD
            }],
            "timestamp": 1768284086,
            "message": GENESIS_MESSAGE
        }

        coinbase["txid"] = self.compute_txid(coinbase)

        block = {
            "block": 0,
            "timestamp": 1768284086,
            "difficulty": self.difficulty,
            "merkle_root": "",
            "transactions":[coinbase],
            "previous_chain": "0" * 64,
            "nonce": 0
        }

        block["merkle_root"] = self.compute_merkle_root(block["transactions"])

        clean = dict(block)
        clean.pop("chain", None)
        clean.pop("nonce", None)

        header = self.serialize(clean).encode()

        seed = self.dsha256_bytes(header)

        buffer = self.build_cpu_buffer(seed)

        start = time.time()

        result = {
            "found": False,
            "nonce": 0,
            "hash": ""
        }

        nonce = 0

        while True:

            h = self.cpu_algorithm(
                buffer,
                seed,
                nonce
            )

            if check_pow(h, self.difficulty):

                result["nonce"] = nonce
                result["hash"] = h
                result["found"] = True

                break

            if nonce % 2000 == 0:

                elapsed = time.time() - start

                if elapsed <= 0:
                    elapsed = 0.001

                hps = nonce / elapsed

                print(
                    f"\r\033[K"
                    f"\r{C.K}⛏ MINING #{0}{C.X} "
                    f"{C.K} NONCE {nonce} "
                    f" {hps:.2f} H/s "
                    f"{C.K} HASH {h[:17]}...{C.X}",
                    end="",
                    flush=True
                )

            nonce += 1

        block["nonce"] = result["nonce"]
        block["chain"] = result["hash"]

        print()

        self.chain.append(block)

        banner("BLOCK FOUND")
        print()

        self.save_chain()

        print(f"GENESIS CREATED")
        print()

    # =====================================
    # TX PAYLOAD
    # =====================================

    def tx_payload(self, tx):
        data = {
            "version": tx["version"],
            "inputs": [{"txid": i["txid"], "vout": i["vout"]} for i in tx["inputs"]],
            "outputs": tx["outputs"],
            "fee": tx.get("fee", 0),
            "timestamp": tx["timestamp"],
            "message": tx.get("message", "")
        }

        return self.serialize(data).encode()

    # =====================================
    # VERIFY SIGNATURE
    # =====================================

    def verify_input(self, tx, idx):
        try:
            inp = tx["inputs"][idx]

            vk = VerifyingKey.from_string(bytes.fromhex(inp["public_key"]), curve=SECP256k1)

            payload = self.tx_payload(tx)

            digest = self.dsha256_bytes(payload)

            sig = bytes.fromhex(inp["signature"])

            return (
                vk.verify_digest(sig, digest, sigdecode=sigdecode_der)
            )

        except Exception:
            return False

    # =====================================
    # VALIDATE TX
    # =====================================

    def validate_tx(self, tx, utxo_set):

        if tx["version"] != VERSION:
            return False, "invalid version"

        message = tx.get("message", "")

        if not isinstance(message, str):
            return False, "invalid message"

        if len(message) > MAX_TX_MESSAGE_LENGTH:
            return False, "message too long"

        if not isinstance(tx["timestamp"], int):
            return False, "invalid timestamp"

        if tx["timestamp"] <= 0:
            return False, "invalid timestamp"

        if not isinstance(tx.get("outputs"), list):
            return False, "invalid outputs"

        if len(tx["outputs"]) == 0:
            return False, "no outputs"

        for o in tx["outputs"]:

            if not isinstance(o, dict):
                return False, "invalid output format"

            if "address" not in o:
                return False, "missing address"

            if not validate_address(o["address"]):
                return False, "bad address"

            if "amount" not in o:
                return False, "missing amount"

            if not isinstance(o["amount"], int):
                return False, "invalid amount"

            if o["amount"] <= 0:
                return False, "invalid amount"

            if o["amount"] > MAX_SUPPLY:
                return False, "amount too large"

        if len(tx["inputs"]) == 0:
            return False, "coinbase not allowed here"

        used = set()
        input_total = 0

        for i, inp in enumerate(tx["inputs"]):

            if not isinstance(inp, dict):
                return False, "invalid input"

            required = [
                "txid",
                "vout",
                "public_key",
                "signature"
            ]

            for field in required:
                if field not in inp:
                    return False, f"missing {field}"

            if not isinstance(inp["vout"], int):
                return False, "invalid vout"

            if inp["vout"] < 0:
                return False, "invalid vout"

            key = (inp["txid"], inp["vout"])

            if key in used:
                return False, "double input"

            used.add(key)

            utxo = next((u for u in utxo_set if u["txid"] == inp["txid"] and u["vout"] == inp["vout"]), None)

            if not utxo or utxo["spent"]:
                return False, "utxo invalid"

            try:
                addr = address_from_pubkey(inp["public_key"])

            except Exception:
                return False, "bad pubkey"

            if normalize_address(addr) != normalize_address(utxo["address"]):
                return False, "bad pubkey"

            if not self.verify_input(tx, i):
                return False, "bad signature"

            input_total += utxo["amount"]

        output_total = sum(o["amount"] for o in tx["outputs"])

        fee = input_total - output_total

        if fee < 0:
             return False, "negative fee"

        tx["fee"] = fee

        if input_total < output_total:
            return False, "insufficient"

        return True, "ok"

    # =====================================
    # APPLY TX
    # =====================================

    def apply_tx(self, tx, utxo_set):

        for inp in tx["inputs"]:
            for u in utxo_set:
                if u["txid"] == inp["txid"] and u["vout"] == inp["vout"]:
                    u["spent"] = True

        for i, out in enumerate(tx["outputs"]):
            utxo_set.append({
                "txid": tx["txid"],
                "vout": i,
                "address": out["address"],
                "amount": out["amount"],
                "spent": False
            })

    # =====================================
    # BLOCK REWARD
    # =====================================

    def get_block_reward(self, height):

        halvings = height // HALVING_INTERVAL

        reward = INITIAL_REWARD // (2 ** halvings)

        return max(reward, 0)

    # =====================================
    # VALIDATE BLOCK
    # =====================================

    def validate_block(self, block, height=None):

        if height is None:
            height = len(self.chain)

        required = [
            "block",
            "timestamp",
            "difficulty",
            "merkle_root",
            "transactions",
            "previous_chain",
            "nonce",
            "chain"
        ]

        for field in required:
            if field not in block:
                return False, f"missing {field}"

        if not isinstance(block["block"], int):
            return False, "bad block"

        if not isinstance(block["timestamp"], int):
            return False, "bad timestamp"

        if not isinstance(block["difficulty"], int):
            return False, "bad difficulty"

        if not isinstance(block["nonce"], int):
            return False, "bad nonce"

        if not isinstance(block["transactions"], list):
            return False, "bad transactions"

        if not isinstance(block["previous_chain"], str):
            return False, "bad previous chain"

        if not isinstance(block["chain"], str):
            return False, "bad chain"

        if not isinstance(block["merkle_root"], str):
            return False, "bad merkle root"

        size = len(self.serialize(block).encode())

        if size > MAX_BLOCK_SIZE:
            return False, "block too large"

        temp_utxo = copy.deepcopy(self.utxos)

        if not isinstance(block["timestamp"], int):
            return False, "bad timestamp"

        if block["timestamp"] <= 0:
            return False, "bad timestamp"

        now = int(time.time())

        if block["timestamp"] > now + MAX_FUTURE_TIME:
            return False, "future block"

        if len(self.chain):

            if block["block"] > 0:

                prev = self.chain[block["block"] - 1]

                if block["timestamp"] <= prev["timestamp"]:
                    return False, "timestamp too old"

        if not isinstance(block["nonce"], int):
            return False, "bad nonce"

        if block["nonce"] < 0:
            return False, "bad nonce"

        if len(block["transactions"]) == 0:
            return False, "no transactions"

        if not isinstance(block["difficulty"], int):
            return False, "bad difficulty"

        if block["difficulty"] != self.difficulty:
            return False, "bad difficulty"

        if block["block"] != height:
            return False, "bad block"

        if block["block"] < 0:
            return False, "negative height"

        if height > 0:

            prev = self.chain[height - 1]

            if block["previous_chain"] != prev["chain"]:
                return False, "bad previous chain"

        # =====================================
        # VERIFY POW
        # =====================================

        clean = dict(block)
        clean.pop("chain", None)
        clean.pop("nonce", None)

        header = self.serialize(clean).encode()

        seed = self.dsha256_bytes(header)

        buffer = self.build_cpu_buffer(seed)

        h = self.cpu_algorithm(
            buffer,
            seed,
            block["nonce"]
        )

        if h != block["chain"]:
            return False, "bad chain"

        if block["merkle_root"] != self.compute_merkle_root(
            block["transactions"]
        ):
            return False, "bad merkle root"

        total_fee = 0
        coinbase = None
        coinbase_count = 0

        for tx in block["transactions"]:

            if not isinstance(tx, dict):
                return False, "invalid transaction"

            expected_txid = self.compute_txid(tx)

            if tx.get("txid") != expected_txid:
                return False, "bad txid"

            if "inputs" not in tx:
                return False, "missing inputs"

            if not isinstance(tx["inputs"], list):
                return False, "invalid inputs"

            if "outputs" not in tx:
                return False, "missing outputs"

            if not isinstance(tx["outputs"], list):
                return False, "invalid outputs"

            if len(tx["inputs"]) == 0:
               coinbase_count += 1
               coinbase = tx

            else:
                valid, reason = self.validate_tx(tx, temp_utxo)
                if not valid:
                    return False, reason

                input_total = sum(
                    u["amount"] for u in temp_utxo
                    if any(
                        u["txid"] == i["txid"] and u["vout"] == i["vout"]
                        for i in tx["inputs"]
                    )
                )

                output_total = sum(o["amount"] for o in tx["outputs"])
                total_fee += tx["fee"]

            self.apply_tx(tx, temp_utxo)

        if coinbase_count != 1:
            return False, "invalid coinbase count"

        if coinbase is None:
            return False, "no coinbase"

        if len(coinbase["outputs"]) != 1:
            return False, "coinbase outputs"

        if len(coinbase["inputs"]) != 0:
            return False, "coinbase inputs"

        if coinbase.get("version") != 1:
            return False, "invalid coinbase version"

        if height == 0:
            if coinbase.get("message") != GENESIS_MESSAGE:
                return False, "invalid genesis message"

        elif height == 1:
            if coinbase.get("message") != BLOCK1_MESSAGE:
                return False, "invalid block 1 message"

        else:
            if coinbase.get("message") != COINBASE_MESSAGE:
                return False, "invalid coinbase message"

        if not isinstance(coinbase.get("timestamp"), int):
            return False, "invalid coinbase timestamp"

        if coinbase["timestamp"] <= 0:
            return False, "invalid coinbase timestamp"

        output = coinbase["outputs"][0]

        if not isinstance(output, dict):
            return False, "invalid coinbase output"

        if not isinstance(output.get("address"), str):
            return False, "invalid coinbase address"

        if not validate_address(output["address"]):
            return False, "invalid coinbase address"

        if not isinstance(output.get("amount"), int):
            return False, "invalid coinbase amount"

        if output["amount"] <= 0:
            return False, "invalid coinbase amount"

        if height == 0:
            reward = INITIAL_REWARD

            if coinbase["outputs"][0]["amount"] != reward:
                return False, "invalid genesis reward"

        else:
            reward = self.get_block_reward(height)

            if reward <= 0:
                return False, "reward finished"

            if self.calculate_supply() + reward > MAX_SUPPLY:
                return False, "max supply exceeded"

            if coinbase["outputs"][0]["amount"] > reward + total_fee:
                return False, "reward too big"

            if not check_pow(h, block["difficulty"]):
                return False, "bad pow"

        return True, "ok"

    # =====================================
    # ADD BLOCK
    # =====================================

    def add_block(self, block):

        with self.lock:

            valid, reason = self.validate_block(block)

            if not valid:
                return {"status": "rejected", "reason": reason}

            for tx in block["transactions"]:
                self.apply_tx(tx, self.utxos)

            self.chain.append(block)
            self.chain_version += 1
            self.save_chain()
            self.adjust_difficulty()
            self.mempool.clear()
            self.txindex.clear()

            return {"status": "accepted"}

    # ==============================================
    # SUPPLY CALCULATE
    # ==============================================

    def calculate_supply(self):

        total = 0

        for block in self.chain:
            for tx in block["transactions"]:

                if len(tx.get("inputs", [])) != 0:
                    continue

                for output in tx.get("outputs", []):
                    total += output["amount"]

        return total

    # =============================================
    # DIFF ADJUST
    # =============================================

    def adjust_difficulty(self):

        height = len(self.chain) - 1

        if height == 0:
            return

        if height % DIFFICULTY_ADJUST_INTERVAL != 0:
            return

        first = self.chain[-DIFFICULTY_ADJUST_INTERVAL - 1]
        last = self.chain[-1]

        actual = last["timestamp"] - first["timestamp"]

        expected = DIFFICULTY_ADJUST_INTERVAL * TARGET_BLOCK_TIME

        if actual < expected:
            self.difficulty = min(MAX_DIFFICULTY,self.difficulty + 1)

        elif actual > expected:
            self.difficulty = max(MIN_DIFFICULTY,self.difficulty - 1)

    # =====================================
    # MINING
    # =====================================

    def mine(self, address):

        block = {
            "block": len(self.chain),
            "timestamp": int(time.time()),
            "difficulty": self.difficulty,
            "merkle_root": "",
            "transactions": [],
            "previous_chain": self.chain[-1]["chain"],
            "nonce": 0
        }

        reward = self.get_block_reward(block["block"])

        total_fee = 0

        for tx in self.mempool:
            total_fee += tx.get("fee", 0)

        height = block["block"]

        if height == 1:
            message = BLOCK1_MESSAGE

        else:
            message = COINBASE_MESSAGE

        coinbase = {
            "version": VERSION,
            "inputs": [],
            "outputs": [{"address": address, "amount": reward + total_fee}],
            "timestamp": int(time.time()),
            "message": message

        }

        coinbase["txid"] = self.compute_txid(coinbase)

        block["transactions"].append(coinbase)
        block["transactions"] += self.mempool

        block["merkle_root"] = self.compute_merkle_root(block["transactions"])

        clean = dict(block)
        clean.pop("chain", None)
        clean.pop("nonce", None)

        header = self.serialize(clean).encode()

        seed = self.dsha256_bytes(header)

        buffer = self.build_cpu_buffer(seed)

        # =====================================
        # MULTI PROCESS
        # =====================================

        workers = multiprocessing.cpu_count()

        manager = multiprocessing.Manager()

        result = manager.dict()

        result["found"] = False
        result["nonce"] = 0
        result["hash"] = ""
        result["count"] = 0


        jobs = []

        processes = []


        for i in range(workers):

            job = (
                self.cpu_algorithm,
                buffer,
                seed,
                self.difficulty,
                i,
                workers,
                result
            )

            p = multiprocessing.Process(target=mine_worker,args=(job,))

            p.start()
            processes.append(p)


        while not result["found"]:

            time.sleep(1)

            print(
                f"\r⛏ Nonce {result['nonce']}",
                end="",
                flush=True
            )


        for p in processes:
            p.terminate()


        block["nonce"] = result["nonce"]
        block["chain"] = result["hash"]

        result = self.add_block(block)

        if result["status"] == "accepted":
            self.mempool = []

        return result

    # =======================================
    # ADD TX
    # =======================================

    def add_transaction(self, tx):

        tx.pop("txid", None)

        valid, reason = self.validate_tx(tx, self.utxos)

        if not valid:
            return {"status": "rejected", "reason": reason}

        tx["txid"] = self.compute_txid(tx)

        if tx["txid"] in self.txindex:
            return {"status": "rejected", "reason": "duplicate"}

        self.mempool.append(tx)
        self.txindex.add(tx["txid"])

        return {"status": "accepted", "txid": tx["txid"]}

    # =====================================
    # BALANCE
    # =====================================

    def get_balance(self, address):
        return sum(u["amount"] for u in self.utxos if u["address"] == address and not u.get("spent", False))

    # =====================================
    # GET UTXO ADDRESS
    # =====================================

    def get_utxos(self, address):
        return [
            u for u in self.utxos
            if u["address"] == address and not u.get("spent", False)]

    # =====================================
    # REBUILD UTXO
    # =====================================

    def rebuild_utxo(self):

        self.utxos = []

        for block in self.chain:
            for tx in block["transactions"]:

                if "txid" not in tx:
                    tx["txid"] = self.compute_txid(tx)

                for inp in tx.get("inputs", []):
                    for u in self.utxos:
                        if u["txid"] == inp["txid"] and u["vout"] == inp["vout"]:
                            u["spent"] = True

                if block["block"] == 0 and len(tx["inputs"]) == 0:
                    continue

                for i, out in enumerate(tx.get("outputs", [])):
                    self.utxos.append({
                        "txid": tx["txid"],
                        "vout": i,
                        "address": out["address"],
                        "amount": out["amount"],
                        "spent": False,
                        "block_height": block["block"]
                    })

        self.txindex = set()

        for block in self.chain:
            for tx in block["transactions"]:
             self.txindex.add(tx["txid"])

# =========================================
# RUN
# =========================================

blockchain = None

def get_blockchain():
    global blockchain

    if blockchain is None:
        blockchain = Blockchain()

    return blockchain

