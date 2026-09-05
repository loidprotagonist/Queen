import time
import threading
import argparse
import requests
import socket
import json
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS
from urllib.parse import urlparse
from requests.utils import parse_url

from core import get_blockchain
chain = get_blockchain()

from ui import *
from consensus import is_valid_chain, resolve_chain
from core import MAX_BLOCK_SIZE
from flask import Flask, request, jsonify, render_template

# ========================================
# FLASK
# ========================================

app = Flask(__name__)

CORS(app)

# =========================================
# CONFIG
# =========================================

VERSION = 1

MAX_PEERS = 1024

SYNC_INTERVAL = 16

MAX_MEMPOOL = 2_000_000

peers = set()

MY_NODE = None

seen_blocks = set()

SEED_NODES = ["http://127.0.0.1:5000"]

PEERS_FILE = "peers.json"

known_peers = set()

# WEB EXPLORER
@app.route("/explorer")
def explorer():
    return render_template("index.html")

# =========================================
# HELPERS
# =========================================

def ok(data=None):
    return jsonify({"status": "ok", "data": data or {}})

# STATUS
def error(reason):
    return jsonify({"status": "error", "reason": reason})

# SAVE PEER
def save_known_peers():
    try:
        with open(PEERS_FILE, "w") as f:
            json.dump(sorted(known_peers), f, indent=2)
    except Exception as e:
        print(f"❌ SAVE PEERS: {e}")

# LOAD PEER
def load_known_peers():
    global known_peers

    try:
        with open(PEERS_FILE, "r") as f:
            data = json.load(f)

        if isinstance(data, list):
            for peer in data:
                if (
                    isinstance(peer, str)
                    and valid_peer(peer)
                    and peer != MY_NODE
                ):
                    known_peers.add(peer)

        banner(f"KNOWN PEERS: {len(known_peers)}")
        print()

    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"❌ LOAD PEERS: {e}")

# LOCAL IP
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

# ========================================
# VALID PEERS
# ========================================

def valid_peer(node):
    try:
        u = parse_url(node)

        if u.scheme not in ("http", "https"):
            return False

        if not u.host:
            return False

        if u.port is not None and not (1 <= u.port <= 65535):
            return False

        if len(u.host) > 253:
            return False

        for label in u.host.split("."):
            if not label or len(label) > 63:
                return False

        return True

    except Exception:
        return False

# =========================================
# CHECK
# =========================================

def is_hybrid_format(tx):

    inputs = tx.get("inputs", [])

    if not isinstance(inputs, list):
        return False

    if len(inputs) == 0:
        return True

    for inp in inputs:
        required = [
            "public_key",
            "signature"
        ]

        if not isinstance(inp, dict):
            return False

        for r in required:
            if r not in inp:
                return False

    return True

# =========================================
# TX EXISTS
# =========================================

def tx_exists(txid):

    for tx in chain.mempool:
        if tx["txid"] == txid:
            return True

    for block in chain.chain:
        for tx in block["transactions"]:
            if tx["txid"] == txid:
                return True

    return False

# =========================================
# DOUBLE SPEND CHECK
# =========================================

def is_double_spend(tx):

    for mem in chain.mempool:
        for i in mem["inputs"]:
            for j in tx.get("inputs", []):
                if i["txid"] == j["txid"] and i["vout"] == j["vout"]:
                    return True

    return False

# ========================================
# PEER
# ========================================

@app.route("/peers")
def get_peers():
    return jsonify({
        "peers": list(peers)
    })

# =========================================
# HOME
# =========================================

@app.route("/")
def home():
    return jsonify({
        "currency": "Queen",
        "version": VERSION,
        "height": len(chain.chain),
        "difficulty": chain.difficulty,
        "mempool": len(chain.mempool),
        "peers": len(peers),
        "supply": chain.calculate_supply(),
        "max_supply": chain.total_supply
    })

# =========================================
# BALANCE
# =========================================

@app.route("/balance/<address>")
def get_balance(address):
    balance = chain.get_balance(address)
    return jsonify({"balance": balance})

# =========================================
# UTXO ADDRESS
# =========================================

@app.route("/utxo/<address>")
def get_utxo_address(address):
    utxos = chain.get_utxos(address)
    return jsonify({"utxos": utxos})

# =========================================
# UTXO
# =========================================

@app.route("/utxo")
def get_all_utxo():
    return jsonify(chain.utxos)

# =========================================
# CHAIN
# =========================================

@app.route("/chain")
def get_chain():
    return jsonify({
        "length": len(chain.chain),
        "chain": chain.chain
    })

# =========================================
# INFO
# =========================================

@app.route("/info")
def get_info():

    height = len(chain.chain)
    reward = chain.get_block_reward(height)

    return jsonify({
        "height": height,
        "difficulty": chain.difficulty,
        "reward": reward,
        "mempool": len(chain.mempool),
        "supply": chain.calculate_supply(),
        "max_supply": chain.total_supply
    })

# =========================================
# SUBMIT BLOCK
# =========================================

@app.route("/submit_block", methods=["POST"])
def submit_block():

    try:
        block = request.get_json(silent=True)

        if block is None:
            return jsonify({
                "status": "error",
                "reason": "invalid json"
            })

        if not isinstance(block, dict):
            return jsonify({
                "status": "error",
                "reason": "invalid block"
            })

        if not block:
            return jsonify({"status": "error", "reason": "empty block"})

        # TXID
        txs = block.get("transactions")

        if txs is None:
            return jsonify({
               "status": "rejected",
               "reason": "missing transactions"
            })

        if not isinstance(txs, list):
            return jsonify({
               "status": "rejected",
               "reason": "invalid transactions"
            })

        if len(txs) == 0:
            return error("empty block")

        for tx in txs:
            if not isinstance(tx, dict):
                return jsonify({
                    "status": "rejected",
                    "reason": "invalid transaction"
                })

            if "txid" not in tx:
                tx["txid"] = chain.compute_txid(tx)

        result = chain.add_block(block)

        if result["status"] != "accepted":
            return jsonify(result)

        height = len(chain.chain) - 1

        txids = set(tx["txid"] for tx in block["transactions"])

        chain.mempool = [
            m for m in chain.mempool
            if m["txid"] not in txids
        ]

        banner(f"BLOCK ACCEPTED ⛏  #{height}")

        broadcast_block(block)

        seen_blocks.add(get_block_id(block))

        return jsonify({
            "status": "accepted",
            "height": height
        })

    except Exception as e:
        import traceback
        print("❌ ERROR SUBMIT BLOCK:")
        traceback.print_exc()

        return jsonify({
            "status": "error",
            "reason": str(e)
        })

# =========================================
# ADD TRANSACTION
# =========================================

@app.route("/transaction", methods=["POST"])
def add_transaction():

    tx = request.get_json(silent=True)

    if tx is None:
        return error("invalid json")

    if not isinstance(tx, dict):
        return error("tx must be object")

    if not tx:
        return error("empty tx")

    required = [
        "version",
        "inputs",
        "outputs",
        "fee",
        "timestamp"
    ]

    for field in required:
        if field not in tx:
            return error(f"missing field: {field}")

    if not is_hybrid_format(tx):
        return error("invalid hybrid format")

    raw_size = len(json.dumps(tx))

    if raw_size > MAX_BLOCK_SIZE:
        return error("tx too large")

    if len(tx.get("message", "")) > 10000:
        return error("message too large")

    tx["txid"] = chain.compute_txid(tx)
    txid = tx["txid"]

    if tx_exists(txid):
        return error("duplicate tx")

    if is_double_spend(tx):
        return error("double spend")

    if len(tx.get("inputs", [])) == 0:
         return error("coinbase not allowed")

    if len(chain.mempool) >= MAX_MEMPOOL:
        return error("mempool full")

    result = chain.add_transaction(tx)

    if result["status"] == "accepted":

        banner(f"✅ TX ACCEPTED {txid[:64]}")

        broadcast_tx(tx)

    return jsonify(result)

# =========================================
# RECEIVE TX
# =========================================

@app.route("/receive_tx", methods=["POST"])
def receive_tx():

    data = request.get_json(silent=True)

    if data is None:
        return error("invalid json")

    if not isinstance(data, dict):
        return error("request must be object")

    if not data:
        return error("empty data")

    tx = data.get("tx")

    if not tx:
        return error("tx missing")

    if not isinstance(tx, dict):
        return error("invalid tx")

    if len(tx.get("outputs", [])) == 0:
        return error("empty outputs")

    if not is_hybrid_format(tx):
        return error("invalid hybrid format")

    tx["txid"] = chain.compute_txid(tx)
    txid = tx["txid"]

    if tx_exists(txid):
        return ok({"message": "already have tx"})

    if is_double_spend(tx):
        return error("double spend")

    banner("✅ RECEIVE TX {txid[:64]}")

    result = chain.add_transaction(tx)

    if result["status"] == "accepted":

        banner("✅ TX RELAYED {txid[:64]}")

        broadcast_tx(tx)

    return jsonify(result)

# =========================================
# BLOCK ID
# =========================================

def get_block_id(block):
    return (
        block.get("block"),
        block.get("previous_chain"),
        block.get("merkle_root"),
        block.get("nonce"),
        block.get("chain")
    )

# =========================================
# RECEIVE BLOCK
# =========================================

@app.route("/receive_block", methods=["POST"])
def receive_block():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error("request must be object")

    block = data.get("block")

    if not isinstance(block, dict):
        return error("invalid block")

    block_id = get_block_id(block)

    # =====================================
    # ALREADY SEEN
    # =====================================

    if block_id in seen_blocks:
        return jsonify({
            "status": "already_seen"
        })

    txs = block.get("transactions")

    if not isinstance(txs, list):
        return error("invalid transactions")

    if len(txs) == 0:
        return error("empty block")

    for tx in txs:

        if not isinstance(tx, dict):
            return error("invalid transaction")

        if "txid" not in tx:
            tx["txid"] = chain.compute_txid(tx)

    banner("BLOCK ⛏  #{block.get('block')} RECEIVED")

    result = chain.add_block(block)

    if result["status"] == "accepted":

        seen_blocks.add(block_id)

        banner("BLOCK ACCEPTED ⛏  #{block.get('block')}")

        txids = {
            tx["txid"]
            for tx in block["transactions"]
        }

        chain.mempool = [
            m for m in chain.mempool
            if m["txid"] not in txids
        ]

        banner("RELAY BLOCK ⛏  #{block.get('block')}")

        broadcast_block(block)

    return jsonify(result)

# =========================================
# MEMPOOL
# =========================================

@app.route("/mempool")
def get_mempool():
    return jsonify({
        "count": len(chain.mempool),
        "mempool": chain.mempool
    })

# =========================================
# ADD PEER
# =========================================

@app.route("/add_peer", methods=["POST"])
def add_peer():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error("request must be object")

    node = str(data.get("node", "")).strip()

    if not node:
        return error("node missing")

    if node == MY_NODE:
        return error("self connection")

    if not valid_peer(node):
        return error("invalid peer")

    if node not in peers:

        if len(peers) >= MAX_PEERS:
            return error("peer limit")

        peers.add(node)
        known_peers.add(node)
        save_known_peers()

        banner(f"PEER ADDED {node}")
        print()

    return jsonify({
        "status": "connected",
        "peers": list(peers)
    })

# =========================================
# BROADCAST TX
# =========================================

def broadcast_tx(tx):

    dead = []

    for peer in list(peers):

        try:

            requests.post(
                f"{peer}/receive_tx",
                json={"tx": tx},
                timeout=3
            )

        except Exception:

            dead.append(peer)

    for p in dead:
        peers.discard(p)
        known_peers.discard(p)

        print(f"❌ REMOVE PEER {p}")

    if dead:
        save_known_peers()

# =========================================
# BROADCAST BLOCK
# ==========================================

def broadcast_block(block):

    dead = []

    for peer in list(peers):

        try:

            requests.post(
                f"{peer}/receive_block",
                json={"block": block},
                timeout=5
            )

        except Exception:

            dead.append(peer)

    for p in dead:
        peers.discard(p)
        known_peers.discard(p)

        print(f"❌ REMOVE PEER {p}")

    if dead:
        save_known_peers()

# ========================================
# SEED
# ========================================

def connect_seed():

    for seed in SEED_NODES:

        if seed == MY_NODE:
            continue

        try:

            requests.post(
                f"{seed}/add_peer",
                json={"node": MY_NODE},
                timeout=5
            )

            banner(f"CONNECTED SEED {seed}")

        except Exception:
            print(f"❌ SEED OFFLINE {seed}")

# ===============================================
# DISCOVER
# ===============================================

def discover_peers():

    for peer in list(peers):

        try:
            r = requests.get(
                f"{peer}/peers",
                timeout=3
            )

            if not r.ok:
                continue

            remote_peers = r.json().get("peers", [])

            if not isinstance(remote_peers, list):
                continue

            for candidate in remote_peers:

                if not isinstance(candidate, str):
                    continue

                if candidate == MY_NODE:
                    continue

                if candidate in peers:
                    continue

                if len(peers) >= MAX_PEERS:
                    return

                if not valid_peer(candidate):
                    continue

                try:
                    requests.post(
                        f"{candidate}/add_peer",
                        json={"node": MY_NODE},
                        timeout=3
                    )

                    peers.add(candidate)
                    known_peers.add(candidate)
                    save_known_peers()

                    banner(f"DISCOVERED {candidate}")

                except Exception as e:
                    print(f"❌ HANDSHAKE {candidate}: {e}")

        except Exception as e:
            print(f"❌ DISCOVERY {peer}: {e}")

# =========================================
# SYNC LOOP
# =========================================

def sync_loop():

    while True:

        time.sleep(SYNC_INTERVAL)

        try:
            discover_peers()
        except Exception as e:
            print(f"❌ DISCOVERY FAIL: {e}")

        for peer in list(peers):
            banner(f"SYNC -> {peer}")

            try:

                # GOSIP PROTOCOL
                try:

                    r = requests.get(f"{peer}/peers", timeout=5)

                    remote_peers = r.json().get("peers", [])

                    if len(remote_peers) > MAX_PEERS:
                        remote_peers = remote_peers[:MAX_PEERS]

                    for p in remote_peers:

                        if p == MY_NODE:
                            continue

                        if len(peers) >= MAX_PEERS:
                            break

                        if p not in peers:
                            peers.add(p)
                            known_peers.add(p)
                            save_known_peers()

                            banner(f"DISCOVERED {p}")

                            try:
                                requests.post(
                                    f"{p}/add_peer",
                                    json={"node": MY_NODE},
                                    timeout=3

                                )

                            except Exception as e:
                                print(e)

                except:
                    pass

                # CHAIN SYNC
                res = requests.get(f"{peer}/chain", timeout=10)

                data = res.json()

                incoming = data.get("chain", [])

                if len(incoming) > 100000:
                    print("❌ CHAIN TOO LARGE")
                    continue

                if not incoming:
                    continue

                if not is_valid_chain(incoming):
                    print(f"❌ INVALID CHAIN FROM {peer}")
                    continue

                new_chain = resolve_chain(chain.chain, incoming)

                if new_chain is not chain.chain:

                    chain.chain = new_chain
                    chain.rebuild_utxo()
                    chain.save_chain()
                    chain.chain_version += 1

                    chain.mempool = []

                    banner(f"✅ CHAIN SYNCED FROM {peer}")

                    banner(f"HEIGHT {len(chain.chain)-1} ⛏")

            except Exception as e:
                print(f"❌ SYNC FAIL")
                print(f"Peer : {peer}")
                print(f"Reason : {e}")

                peers.discard(peer)
                known_peers.discard(peer)
                save_known_peers()

# =========================================
# RUN
# =========================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)

    args = parser.parse_args()

    MY_NODE = f"http://127.0.0.1:{args.port}"

    ADVERTISE_NODE = f"http://{get_local_ip()}:{args.port}"

    load_known_peers()

    for peer in list(known_peers):
        if peer == MY_NODE:
           continue

        try:
           requests.post(
               f"{peer}/add_peer",
               json={"node": ADVERTISE_NODE},
               timeout=3
           )

           peers.add(peer)

           banner(f"RECONNECTED {peer}")

        except Exception:
            print(f"❌ PEER OFFLINE {peer}")

    for seed in SEED_NODES:
        if seed != MY_NODE:
            try:
                requests.post(
                    f"{seed}/add_peer",
                    json={"node": MY_NODE},
                    timeout=3
                )

                peers.add(seed)
                known_peers.add(seed)
                save_known_peers()

                banner(f"SEED CONNECTED {seed}")
                time.sleep(0.5)

            except Exception as e:
                print(f"❌ SEED {seed}: {e}")

    print()
    banner(f"NODE STARTED")
    time.sleep(0.5)
    banner(f"NODE {MY_NODE}")
    time.sleep(0.5)
    banner(f"HEIGHT {len(chain.chain)}")
    time.sleep(0.5)

    threading.Thread(
        target=sync_loop,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=args.port,
        threaded=True
    )
