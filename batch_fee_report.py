# batch_fee_report.py
import os
import sys
import csv
import json
import time
import argparse
from typing import Dict, Any, Iterable, List, Tuple
from web3 import Web3

DEFAULT_RPC = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/your_api_key")

NETWORKS = {
    1: "Ethereum Mainnet",
    11155111: "Sepolia Testnet",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum One",
}

def network_name(cid: int) -> str:
    return NETWORKS.get(cid, f"Unknown (chain ID {cid})")

def connect(rpc: str, timeout: float = 25.0) -> Web3:
    start = time.time()
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))

    if not w3.is_connected():
        print("❌ Failed to connect to RPC.", file=sys.stderr)
        sys.exit(1)
    print(f"⚡ Connected to {network_name(w3.eth.chain_id)} (chainId {w3.eth.chain_id}) in {time.time()-start:.2f}s")
    return w3

def is_tx_hash(s: str) -> bool:
    return isinstance(s, str) and s.startswith("0x") and len(s) == 66

def read_hashes(source_file: str | None, limit: int | None) -> List[str]:
    lines: Iterable[str]
    if source_file:
        with open(source_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        if sys.stdin.isatty():
            print("ℹ️  Reading tx hashes from stdin (end with Ctrl-D / Ctrl-Z)...", file=sys.stderr)
        lines = sys.stdin.readlines()

    hashes: List[str] = []
    for raw in lines:
        h = raw.strip()
        if not h:
            continue
        if is_tx_hash(h):
            hashes.append(h)
        else:
            print(f"⚠️  Skipping invalid hash: {h}", file=sys.stderr)
        if limit and len(hashes) >= limit:
            break
    return hashes

def safe_call(fn, *args, retries=2, delay=0.8, **kwargs):
    for attempt in range(1, retries+1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == retries:
                raise
            print(f"⚠️  RPC call failed ({e}); retrying {attempt}/{retries-1}...", file=sys.stderr)
            time.sleep(delay)

def tx_type_label(tt) -> str:
    return {0: "Legacy", 1: "AccessList", 2: "EIP-1559"}.get(tt if isinstance(tt, int) else 0, f"Unknown({tt})")

def summarize_tx(w3: Web3, tx_hash: str, block_cache: Dict[int, Any], latest_block: int) -> Dict[str, Any]:
    # receipt first (has status, gasUsed, blockNumber, effectiveGasPrice)
    rcpt = safe_call(w3.eth.get_transaction_receipt, tx_hash)
    if rcpt is None or rcpt.blockNumber is None:
        return {"txHash": tx_hash, "statusText": "pending_or_not_found"}

    # fetch tx only once for value, gas limit, type, from/to (receipt may contain from/to on some clients)
    tx = safe_call(w3.eth.get_transaction, tx_hash)

    block_num = int(rcpt.blockNumber)
    block = block_cache.get(block_num)
    if block is None:
        block = safe_call(w3.eth.get_block, block_num)
        block_cache[block_num] = block

    ts = int(block.timestamp)
    base_fee_wei = int(block.get("baseFeePerGas", 0) or 0)

    eff_price_wei = getattr(rcpt, "effectiveGasPrice", None)
    if eff_price_wei is None:
        eff_price_wei = int(tx.get("gasPrice", 0) or 0)

    tip_wei = max(0, int(eff_price_wei) - base_fee_wei)
    total_fee_eth = float(Web3.from_wei(int(rcpt.gasUsed) * int(eff_price_wei), "ether"))

    gas_limit = int(getattr(tx, "gas", tx.get("gas", 0)))
    gas_eff = (int(rcpt.gasUsed) / gas_limit * 100.0) if gas_limit else None

    age_min = (time.time() - ts) / 60.0
    confirmations = max(0, int(latest_block) - block_num)

    # tx type; web3 may give int in tx['type'] or None
    raw_type = tx.get("type", 0)
    if isinstance(raw_type, bytes):
        # some clients return hex as bytes; convert if needed
        try:
            raw_type = int.from_bytes(raw_type, "big")
        except Exception:
            raw_type = 0

    return {
        "txHash": tx_hash,
        "status": int(rcpt.status),
        "blockNumber": block_num,
        "timestamp": ts,
        "utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts)),
        "confirmations": confirmations,
        "from": tx["from"],
        "to": tx["to"],
        "valueEth": float(Web3.from_wei(tx.get("value", 0), "ether")),
        "gasUsed": int(rcpt.gasUsed),
        "gasLimit": gas_limit,
        "gasEfficiencyPct": round(gas_eff, 2) if gas_eff is not None else None,
        "effectiveGasPriceGwei": float(Web3.from_wei(eff_price_wei, "gwei")),
        "baseFeeAtTxGwei": float(Web3.from_wei(base_fee_wei, "gwei")),
        "tipAtTxGwei": float(Web3.from_wei(tip_wei, "gwei")),
        "totalFeeEth": total_fee_eth,
        "txType": tx_type_label(int(raw_type) if raw_type is not None else 0),
        "ageMinutes": round(age_min, 2),
    }

def to_csv(rows: List[Dict[str, Any]], out_path: str | None):
    if not rows:
        print("⚠️  No rows to write.", file=sys.stderr)
        return
    # consistent column order
    cols = [
        "txHash","status","txType","blockNumber","utc","confirmations",
        "from","to","valueEth",
        "gasUsed","gasLimit","gasEfficiencyPct",
        "effectiveGasPriceGwei","baseFeeAtTxGwei","tipAtTxGwei","totalFeeEth",
        "ageMinutes"
    ]
    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"📄 CSV written to {out_path}")
    else:
        w = csv.DictWriter(sys.stdout, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Batch analyze transaction fees and efficiency; outputs CSV or JSON."
    )
    ap.add_argument("--rpc", default=DEFAULT_RPC, help="RPC URL (default from RPC_URL env)")
        ap.add_argument(
        "--timeout",
        type=float,
        default=25.0,
        help="RPC timeout in seconds (default: 25)",
    )
    ap.add_argument("--file", help="File with one tx hash per line (default: stdin)")
    ap.add_argument("--limit", type=int, help="Limit number of hashes read")
    ap.add_argument("--out", help="CSV output path (default: stdout)")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of CSV")
    return ap.parse_args()

def main():
    args = parse_args()
      print(f"🔗 Using RPC endpoint: {args.rpc}")
    hashes = read_hashes(args.file, args.limit)
    print(f"🧮 Processing {len(hashes)} transaction hashes…")
    if not hashes:
        print("❌ No valid transaction hashes provided.", file=sys.stderr)
        sys.exit(1)

    w3 = connect(args.rpc)
    latest = int(w3.eth.block_number)
    cache: Dict[int, Any] = {}
    rows: List[Dict[str, Any]] = []

    t0 = time.time()
    for i, h in enumerate(hashes, 1):
        try:
            row = summarize_tx(w3, h, cache, latest)
            rows.append(row)
        except Exception as e:
            print(f"⚠️  Failed to process {h}: {e}", file=sys.stderr)
        if i % 10 == 0:
            print(f"🔍 Processed {i}/{len(hashes)}...", file=sys.stderr)

    if args.json:
        print(json.dumps({
            "network": network_name(w3.eth.chain_id),
            "chainId": int(w3.eth.chain_id),
            "count": len(rows),
            "generatedAtUtc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "rows": rows
        }, indent=2, sort_keys=True))
    else:
        to_csv(rows, args.out)

    print(f"⏱️  Elapsed: {time.time() - t0:.2f}s", file=sys.stderr)

if __name__ == "__main__":
    main()
