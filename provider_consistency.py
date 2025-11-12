# provider_consistency.py
import os
import sys
import time
import argparse
from typing import Dict, Any
from web3 import Web3

DEFAULT_RPC1 = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/your_api_key")
DEFAULT_RPC2 = os.getenv("RPC_URL_2", "https://rpc.ankr.com/eth")

NETWORKS = {
    1: "Ethereum Mainnet",
    11155111: "Sepolia Testnet",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum One",
}

def network_name(cid: int) -> str:
    return NETWORKS.get(cid, f"Unknown (chain ID {cid})")

def connect(url: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 25}))
    print(f"🧠 Client: {w3.client_version}")
    if not w3.is_connected():
        print(f"❌ Failed to connect: {url}")
        sys.exit(1)
    return w3

def tx_commitment(chain_id: int, tx_hash: str, rcpt) -> str:
    """
    keccak(chainId[8] || txHash[32] || blockNumber[8] || status[1] || gasUsed[8])
    """
    payload = (
        int(chain_id).to_bytes(8, "big")
        + bytes.fromhex(tx_hash[2:])
        + int(rcpt.blockNumber).to_bytes(8, "big")
        + int(rcpt.status).to_bytes(1, "big")
        + int(rcpt.gasUsed).to_bytes(8, "big")
    )
    return "0x" + Web3.keccak(payload).hex()

def header_commitment(chain_id: int, header) -> str:
    """
    keccak(
      chainId[8] || number[8] || hash[32] || parentHash[32] ||
      stateRoot[32] || receiptsRoot[32] || transactionsRoot[32] || timestamp[8]
    )
    """
    fields = (
        int(chain_id).to_bytes(8, "big")
        + int(header.number).to_bytes(8, "big")
        + bytes.fromhex(header.hash.hex()[2:])
        + bytes.fromhex(header.parentHash.hex()[2:])
        + bytes.fromhex(header.stateRoot.hex()[2:])
        + bytes.fromhex(header.receiptsRoot.hex()[2:])
        + bytes.fromhex(header.transactionsRoot.hex()[2:])
        + int(header.timestamp).to_bytes(8, "big")
    )
    return "0x" + Web3.keccak(fields).hex()

def compare_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, bool]:
    return {k: (a.get(k) == b.get(k)) for k in sorted(set(a.keys()) | set(b.keys()))}

def fetch_tx_bundle(w3: Web3, tx_hash: str) -> Dict[str, Any]:
    rcpt = w3.eth.get_transaction_receipt(tx_hash)
    if rcpt is None or rcpt.blockNumber is None:
        return {"statusText": "pending_or_not_found"}
    chain_id = w3.eth.chain_id
    return {
        "chainId": int(chain_id),
        "network": network_name(int(chain_id)),
        "tx": tx_hash,
        "blockNumber": int(rcpt.blockNumber),
        "status": int(rcpt.status),
        "gasUsed": int(rcpt.gasUsed),
        "commitment": tx_commitment(chain_id, tx_hash, rcpt),
    }

def fetch_block_bundle(w3: Web3, block_id) -> Dict[str, Any]:
    header = w3.eth.get_block(block_id)
    chain_id = w3.eth.chain_id
    return {
        "chainId": int(chain_id),
        "network": network_name(int(chain_id)),
        "number": int(header.number),
        "hash": header.hash.hex(),
        "parentHash": header.parentHash.hex(),
        "stateRoot": header.stateRoot.hex(),
        "receiptsRoot": header.receiptsRoot.hex(),
        "transactionsRoot": header.transactionsRoot.hex(),
        "timestamp": int(header.timestamp),
        "commitment": header_commitment(chain_id, header),
    }

def parse_args():
    ap = argparse.ArgumentParser(
        description="Cross-verify soundness of a tx or block across two RPC providers."
    )
    ap.add_argument("--rpc1", default=DEFAULT_RPC1, help="Primary RPC URL")
    ap.add_argument("--rpc2", default=DEFAULT_RPC2, help="Secondary RPC URL")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tx", help="Transaction hash (0x...) to compare")
    mode.add_argument("--block", help="Block tag/number: latest|finalized|safe|pending or integer")
    ap.add_argument("--json", action="store_true", help="Print JSON result")
    return ap.parse_args()

def as_int_or_tag(s: str):
    if s is None:
        return "latest"
    low = s.lower()
    if low in ("latest", "finalized", "safe", "pending"):
        return low
    return int(s, 0)

def main():
    args = parse_args()
    t0 = time.time()
    w3a = connect(args.rpc1)
    w3b = connect(args.rpc2)

    if args.tx:
        if not (args.tx.startswith("0x") and len(args.tx) == 66):
            print("❌ Invalid tx hash.")
            sys.exit(1)
        a = fetch_tx_bundle(w3a, args.tx)
        b = fetch_tx_bundle(w3b, args.tx)

        if a.get("statusText") == "pending_or_not_found" or b.get("statusText") == "pending_or_not_found":
            print("⏳ Pending or not found on at least one provider.")
            sys.exit(0)

        cmp = compare_dicts(a, b)
        if args.json:
            import json
            print(json.dumps({"primary": a, "secondary": b, "match": cmp}, indent=2, sort_keys=True))
            return

        print(f"🌐 PRIMARY: {a['network']} (chainId {a['chainId']})  🔗 {args.tx}")
        print(f"   block={a['blockNumber']} status={a['status']} gasUsed={a['gasUsed']} commit={a['commitment']}")
        print(f"🌐 SECOND.: {b['network']} (chainId {b['chainId']})  🔗 {args.tx}")
        print(f"   block={b['blockNumber']} status={b['status']} gasUsed={b['gasUsed']} commit={b['commitment']}")
        print("\n— Comparison —")
        for k in ["chainId", "blockNumber", "status", "gasUsed", "commitment"]:
            print(f"{k:12s}: {'✅' if cmp[k] else '❌'}")
        if all(cmp.values()):
            print("🔒 Soundness confirmed for tx across providers.")
        else:
            print("⚠️  Inconsistencies detected. Re-check providers or try again with a specific block tag.")

    else:
        block_id = as_int_or_tag(args.block)
        a = fetch_block_bundle(w3a, block_id)
        # Resolve exact number on secondary if tag used, to compare the same number
        b_block_id = a["number"] if not isinstance(block_id, int) else block_id
        b = fetch_block_bundle(w3b, b_block_id)

        cmp = compare_dicts(a, b)
        if args.json:
            import json
            print(json.dumps({"primary": a, "secondary": b, "match": cmp}, indent=2, sort_keys=True))
            return

        print(f"🌐 PRIMARY: {a['network']} (chainId {a['chainId']})  🔢 {a['number']}")
        print(f"   hash={a['hash']}")
        print(f"🌐 SECOND.: {b['network']} (chainId {b['chainId']})  🔢 {b['number']}")
        print(f"   hash={b['hash']}")
        print("\n— Comparison —")
        for k in ["chainId", "number", "hash", "parentHash", "stateRoot", "receiptsRoot", "transactionsRoot", "timestamp", "commitment"]:
            print(f"{k:15s}: {'✅' if cmp.get(k, False) else '❌'}")
        if all(cmp.get(k, False) for k in ["chainId", "number", "hash", "parentHash", "stateRoot", "receiptsRoot", "transactionsRoot", "timestamp", "commitment"]):
            print("🔒 Soundness confirmed for header across providers.")
        else:
            print("⚠️  Inconsistencies detected. Consider using an exact block number or different providers.")

    print(f"\n⏱️  Elapsed: {time.time() - t0:.2f}s")

if __name__ == "__main__":
    main()
