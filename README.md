<p align="center">
  <img src="Logo.png" width="180">
</p>

# QUEEN
# $LOID
# Electronic Cash System

Queen is an experimental peer-to-peer electronic cash system written in Python.

The project explores a simple blockchain architecture with:

- Proof of Work (PoW)
- SHA-256 based hashing
- UTXO transaction model
- Merkle roots
- Cryptographic wallet addresses
- Block and transaction verification
- Node-based blockchain operation
- CPU mining
- Chain validation

«Don't Trust. Verify.»

Queen is an experimental project and is not production-ready.

Documentation

Queen Paper

The technical design and architecture of Queen are documented in the project paper:

"Read the Queen Paper"

The paper describes the system architecture, blockchain structure, transaction model, Proof of Work, verification process, and other design concepts behind Queen.

«Paper: https://drive.google.com/file/d/1nfD79S52X1nFtw4q8Y4oMiYYc8eOF912/view?usp=drivesdk»

---

Features

Blockchain

Each block contains information such as:

- Block height
- Timestamp
- Difficulty
- Merkle root
- Transactions
- Previous block hash
- Nonce
- Proof-of-Work result

The block hash is independently reproducible from the block data, nonce, and mining algorithm.

Proof of Work

Miners repeatedly test different nonce values until the resulting hash satisfies the network target.

Example:

Block        : 0
Difficulty   : 1
Nonce        : 3232863
Chain        : 0000076817c4822c174530ec4a33b3b51a7fa737a01fe4e23f87fcd3b31599d6

A valid block can then be verified independently.

Transactions

Queen uses a UTXO-based transaction model.

Transactions contain:

- Inputs
- Outputs
- Transaction ID (TXID)
- Version
- Timestamp
- Message

Verification

Queen includes a block verifier.

The verifier recalculates the block result and compares it with the stored chain value.

Example:

Stored    : 0000076817c4822c174530ec4a33b3b51a7fa737a01fe4e23f87fcd3b31599d6

Result    : 0000076817c4822c174530ec4a33b3b51a7fa737a01fe4e23f87fcd3b31599d6

Status    : VALID
Match     : True

The purpose is simple:

Do not trust the stored hash. Calculate it again.

---

Requirements

Queen is written in Python.

Recommended:

Python 3.10+

The project may also work on other Python versions, but compatibility can vary depending on the platform and dependencies.

You need:

- Python
- pip
- Git
- A terminal

For CPU mining, performance depends heavily on the device and CPU.

---

Running Queen

Linux

Clone the repository:

git clone https://github.com/loidprotagonist/Queen.git
cd Queen

Install dependencies:

python3 -m pip install -r requirements.txt

Run the node:

python3 Loid_node.py

In another terminal, run the miner:

python3 Loid_miner.py

Run the verifier:

python3 Loid_verify.py

Run the wallet:

python3 Loid_wallet.py

---

Android / Termux

Install Python and Git:

pkg update
pkg install python git

Clone Queen:

git clone https://github.com/loidprotagonist/Queen.git
cd Queen

Install dependencies:

pip install -r requirements.txt

Run the node:

python Loid_node.py

Run the miner:

python Loid_miner.py

Run the verifier:

python Loid_verify.py

Run the wallet:

python Loid_wallet.py

CPU mining performance on Android devices will vary significantly between devices.

---

Other Platforms

Queen is Python-based, so it may run on other operating systems that provide a compatible Python environment.

The general procedure is:

git clone https://github.com/loidprotagonist/Queen.git
cd Queen

Install dependencies:

python -m pip install -r requirements.txt

Then run the desired component:

python Loid_node.py
python Loid_miner.py
python Loid_verify.py
python Loid_wallet.py

The exact command may differ depending on the operating system.

---

Mining

Start the miner:

python Loid_miner.py

The miner displays information such as:

MINING #0
NONCE 3212000
HASHRATE 3272 H/s
HASH ...

When a valid Proof of Work is found:

===================================
       BLOCK FOUND
===================================

The block is then submitted to the node for validation.

The node may reject a block if its Proof of Work or other consensus rules are invalid.

---

Project Structure

The project is organized around the following components:

Loid_core.py
    Core blockchain functions

Loid_consensus.py
    Consensus and validation rules

Loid_node.py
    Blockchain node and network interface

Loid_miner.py
    CPU Proof-of-Work miner

Loid_transaction.py
    Transaction handling

Loid_wallet.py
    Wallet and address handling

Loid_verify.py
    Blockchain verification

Loid_ui.py
    Terminal interface

Additional testing and utility scripts are included in the repository.

---

Experimental Status

Queen is an experimental blockchain project.

It has been developed and tested primarily in a Python environment and on Android/Termux.

It has not been presented as production-grade financial software.

Important areas are still subject to change, including:

- Consensus rules
- Networking
- Wallet implementation
- Transaction validation
- Mining implementation
- Difficulty adjustment
- Security
- Performance
- Database/storage design

Do not use Queen for real funds or security-critical applications.

---

Reporting Problems

If Queen does not work on your device, feedback is welcome.

Please include as much information as possible so the problem can be reproduced.

Include:

1. Operating system

Linux / Android / Termux / Windows / etc.

2. Python version

python --version

3. Command used

Example:

python mining.py

4. Full error message / traceback

Please copy the complete error instead of only writing:

it doesn't work

For example:

Traceback (most recent call last):
    ...

5. Hardware information

If the problem is related to mining performance, include the CPU/device model.

---

Feedback

Bug reports, compatibility reports, testing results, and technical feedback are welcome.

If something does not work, please report it rather than silently assuming the implementation is correct.

A reproducible bug is more useful than a vague complaint.

«Don't Trust. Verify.»

---

License

See the "LICENSE" file included in this repository.
