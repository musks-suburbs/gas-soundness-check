# app.py
import os
import sys
import time
import json
import argparse
from typing import Any, Dict

from datetime import datetime
import platform

from web3 import Web3

# ---------- Defaults (override via --rpc or environment) ----------
DEFAULT_RPC = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/your_api_key")

NETWORKS = {
    1: "Ethereum Mainnet",
    11155111: "Sepolia Testnet",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum One",
}

# ---------- Small helpers ----------
def network_name(cid: int) -> str:
    return NETWORKS.get(cid, f"Unknown (chain ID {cid})")

def is_tx_hash(s: str) -> bool:
    return isinstance(s, str) and s.startswith("0x") and len(s) == 66

def connect(rpc: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        print(f"❌ Failed to connect to RPC: {rpc}", file=sys.stderr)
        sys.exit(1)
    return w3


def fmt_utc(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts))

# ---------- Core (optimized: minimal RPC calls) ----------
def fetch_tx_summary(w3: Web3, tx_hash: str) -> Dict[str, Any]:
    """
    Fetch a minimal but rich summary of a transaction:
    - network / chain ID
    - status, gas used, gas efficiency
    - block, timestamp, confirmations
    - miner/validator address
    - fee breakdown (gas price, total fee, base fee at block)
    """

    chain_id = w3.eth.chain_id

       # (2) receipt
    try:
        rcpt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        print(f"❌ Failed to fetch receipt: {e}")
        sys.exit(2)

    # Check if tx is still pending
    try:
        tx = w3.eth.get_transaction(tx_hash)
        if tx is not None and tx.blockNumber is None:
            print("⏳ Transaction is pending (not yet included in a block).")
            sys.exit(0)
    except Exception:
        pass

        
        # ✅ New code: check if tx is pending
      try:
        tx = w3.eth.get_transaction(tx_hash)
        gas_limit = tx.gas
        gas_efficiency = (rcpt.gasUsed / gas_limit) * 100 if gas_limit else None


         if rcpt is None or rcpt.blockNumber is None:
        print("❌ Transaction not found or not yet included in a block.")
        sys.exit(0)

    # Calculate gas efficiency (used / limit)
    try:
        tx = w3.eth.get_transaction(tx_hash)
        gas_limit = tx.gas
        gas_efficiency = (rcpt.gasUsed / gas_limit) * 100 if gas_limit else None
    except Exception:
        gas_efficiency = None

        
    # (3) block at tx inclusion
    try:
        block = w3.eth.get_block(rcpt.blockNumber)
    except Exception as e:
        print(f"❌ Failed to fetch tx block: {e}")
        sys.exit(2)
          miner_address = block.get("miner", "N/A")  # ✅ Capture miner/validator

    # (4) latest for confirmations
    latest = w3.eth.block_number
    confirmations = max(0, int(latest) - int(rcpt.blockNumber))

    # Prefer EIP-1559 effectiveGasPrice if available
    gas_price_wei = getattr(rcpt, "effectiveGasPrice", None)
    if gas_price_wei is None:
        # Fallback (legacy clients)
        try:
            # Some clients include 'gasPrice' in receipt; if not, assume 0
            gas_price_wei = int(rcpt.get("gasPrice", 0))  # type: ignore[attr-defined]
        except Exception:
            gas_price_wei = 0

    total_fee_wei = int(rcpt.gasUsed) * int(gas_price_wei or 0)
    
      # Get miner/validator address
    miner_address = getattr(block, "miner", "N/A")

    
    return {
        "miner": miner_address,
         "gasEfficiency": round(gas_efficiency, 2) if gas_efficiency is not None else None,
        "chainId": int(chain_id),
        "miner": miner_address,
        "network": network_name(int(chain_id)),
               "txHash": tx_hash,
        "from": rcpt.get("from", "N/A"),
        "to": rcpt.get("to", "N/A"),
        "status": int(getattr(rcpt, "status", 0)),

        "blockNumber": int(rcpt.blockNumber),
        "timestamp": int(block.timestamp),
        "confirmations": confirmations,
        "gasUsed": int(rcpt.gasUsed),
        "gasPriceGwei": float(Web3.from_wei(gas_price_wei or 0, "gwei")),
        "totalFeeEth": float(Web3.from_wei(total_fee_wei, "ether")),
        "baseFeeAtTxGwei": float(Web3.from_wei(block.get("baseFeePerGas", 0), "gwei")),
    }

# ---------- CLI ----------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Optimized transaction gas & commitment facts (minimal RPC calls)."
    )
    p.add_argument("tx_hash", help="Transaction hash (0x + 64 hex chars)")
    p.add_argument("--rpc", default=DEFAULT_RPC, help="RPC URL (default from RPC_URL env)")
    p.add_argument("--json", action="store_true", help="Print JSON instead of human-readable output")
    p.add_argument("--warn-fee-eth", type=float, default=0.05, help="Warn if fee exceeds this ETH (default 0.05)")
    p.add_argument(
        "--minimal",
        action="store_true",
        help="Print only status and fee (no extra details)",
    )
    return p.parse_args()
def colorize(text, color):
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "reset": "\033[0m",
    }
    prefix = colors.get(color, "")
    reset = colors["reset"] if prefix else ""
    return f"{prefix}{text}{reset}"

def main():
    import platform
    print(f"📦 Running on Python {platform.python_version()} on {platform.system()}")
    args = parse_args()
    if not args.rpc.startswith(("http://", "https://")):
        print("⚠️ RPC URL does not start with http:// or https://; continuing anyway.")
from datetime import datetime
print(f"🕒 Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    if not is_tx_hash(args.tx_hash):
        print("❌ Invalid transaction hash format.")
        sys.exit(1)

    t0 = time.time()
    w3 = connect(args.rpc)
    try:
        cid = w3.eth.chain_id
        print(f"🌐 Detected network: {network_name(cid)} (chainId {cid})")
    except Exception:
        print("🌐 Network detection failed.")
    start_time = time.time()
    print(f"⚡ RPC latency: {time.time() - start_time:.3f}s")
    summary = fetch_tx_summary(w3, args.tx_hash)
    if args.minimal:
        status_text = "success" if summary["status"] == 1 else "failed"
        print(f"📦 Status: {status_text}")
        print(f"💰 Total Fee: {summary['totalFeeEth']:.6f} ETH")
        print(f"⏱️  Elapsed: {time.time() - t0:.2f}s")
        return

    if args.json:
        import json
        # Compact JSON but stable keys
        print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
        return

       print(f"🌐 Connected to {summary['network']} (chainId {summary['chainId']})")
    if summary["chainId"] == 1:
        print(f"🔍 Etherscan: https://etherscan.io/tx/{summary['txHash']}")
    if summary["chainId"] == 1:
        print(f"🔍 Etherscan: https://etherscan.io/tx/{summary['txHash']}")
    elif summary["chainId"] == 137:
        print(f"🔍 Polygonscan: https://polygonscan.com/tx/{summary['txHash']}")
    elif summary["chainId"] == 42161:
        print(f"🔍 Arbiscan: https://arbiscan.io/tx/{summary['txHash']}")


    print(f"👤 From: {summary['from']}")
    to_addr = summary['to'] or "(contract creation)"
    print(f"🎯 To: {to_addr}")

      status_text = "✅ Success" if summary["status"] == 1 else "❌ Failed"
    color = "green" if summary["status"] == 1 else "red"
    print(f"📦 Status: {colorize(status_text, color)}")
    print(f"🔢 Block: {summary['blockNumber']}  🕒 {fmt_utc(summary['timestamp'])} UTC  ✅ Confirmations: {summary['confirmations']}")
    if summary["confirmations"] < 3:
        print("⚠️ Low confirmations: consider waiting for more blocks before relying on this tx.")
    print(f"⛏️  Miner/Validator: {summary['miner']}")
       print(f"⛽ Gas Used: {summary['gasUsed']}")
    gas_eff = summary.get("gasEfficiency")
    if gas_eff is not None:
        print(f"📈 Gas Efficiency: {gas_eff:.2f}% of gas limit used")
    else:
        print("📈 Gas Efficiency: N/A (gas limit unavailable)")

    print(
        f"⛽ Gas Price: {summary['gasPriceGwei']:.2f} Gwei  "
        f"(BaseFee@tx: {summary['baseFeeAtTxGwei']:.2f} Gwei)"
    )


    print(f"💰 Total Fee: {summary['totalFeeEth']:.6f} ETH")
      if args.warn_fee_eth > 0 and summary["totalFeeEth"] > args.warn_fee_eth:
        print(f"⚠️  High Fee Warning: {summary['totalFeeEth']:.4f} ETH exceeds threshold {args.warn_fee_eth:.4f} ETH.")


    print(f"⏱️  Elapsed: {time.time() - t0:.2f}s")

if __name__ == "__main__":
    main()
