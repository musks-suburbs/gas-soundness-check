# app.py
import os
import sys
import time
import argparse
from typing import Any, Dict
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
        print("❌ Failed to connect to RPC.")
        sys.exit(1)
    return w3

def fmt_utc(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts))

# ---------- Core (optimized: minimal RPC calls) ----------
def fetch_tx_summary(w3: Web3, tx_hash: str) -> Dict[str, Any]:
    
    """
    Optimized plan (minimize RPC round-trips):
      1) eth_chainId                                  -> chain id
      2) eth_getTransactionReceipt(tx)                -> status, gasUsed, effGasPrice, blockNumber, from, to
      3) eth_getBlockByNumber(blockNumber, false)     -> timestamp, baseFeePerGas (at tx block)
      4) eth_blockNumber                              -> latest (to compute confirmations)
    No eth_getTransaction call needed (receipt already contains from/to on modern clients).
    """
    chain_id = w3.eth.chain_id

    # (2) receipt
    try:
        rcpt = w3.eth.get_transaction_receipt(tx_hash)
        # Проверяем, не находится ли транзакция в ожидании
tx = w3.eth.get_transaction(tx_hash)
if tx and tx.blockNumber is None:
    print("⏳ Транзакция находится в мемпуле — блок ещё не присвоен.")
    sys.exit(0)

    except Exception as e:
        print(f"❌ Failed to fetch receipt: {e}")
        sys.exit(2)
        
        # ✅ New code: check if tx is pending
      try:
        tx = w3.eth.get_transaction(tx_hash)
        gas_limit = tx.gas
        gas_efficiency = (rcpt.gasUsed / gas_limit) * 100 if gas_limit else None


      if rcpt is None or rcpt.blockNumber is None:
        print("❌ Транзакция не найдена или ещё не включена в блок.")
        sys.exit(0)

        
 # ✅ Calculate gas efficiency (used / limit)
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
    
   # ✅ Get miner/validator address
    miner_address = block.get("miner", "N/A")
    
    return {
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
    return p.parse_args()
def colorize(text, color):
    return text  # простой безопасный вариант без цветов

def main():
    args = parse_args()
from datetime import datetime
print(f"🕒 Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    if not is_tx_hash(args.tx_hash):
        print("❌ Invalid transaction hash format.")
        sys.exit(1)

    t0 = time.time()
    w3 = connect(args.rpc)
    start_time = time.time()
    print(f"⚡ RPC latency: {time.time() - start_time:.3f}s")
    summary = fetch_tx_summary(w3, args.tx_hash)

    if args.json:
        import json
        # Compact JSON but stable keys
        print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
        return
start_time = time.time()
print(f"⏱️  Elapsed: {time.time() - start_time:.2f}s")

    print(f"🌐 Connected to {summary['network']} (chainId {summary['chainId']})")
      if summary["chainId"] == 1:
        print(f"🔍 Etherscan: https://etherscan.io/tx/{summary['txHash']}")

    print(f"👤 From: {summary['from']}")
    to_addr = summary['to'] or "(contract creation)"
    print(f"🎯 To: {to_addr}")

   status_text = "✅ Success" if summary["status"] == 1 else "❌ Failed"
   color = "green" if summary["status"] == 1 else "red"
    print(f"📦 Status: {colorize(status_text, color)}")
    print(f"🔢 Block: {summary['blockNumber']}  🕒 {fmt_utc(summary['timestamp'])} UTC  ✅ Confirmations: {summary['confirmations']}")
    print(f"⛏️  Miner/Validator: {summary['miner']}")
    print(f"⛽ Gas Used: {summary['gasUsed']}")
    gas_eff = summary.get("gasEfficiency")
    print(f"📈 Gas Efficiency: {gas_eff:.2f}% of gas limit used" if gas_eff is not None else "📈 Gas Efficiency: N/A (gas limit unavailable)")

else:
    print("📈 Gas Efficiency: N/A (gas limit unavailable)")
print(f"⛽ Gas Price: {summary['gasPriceGwei']:.2f} Gwei  (BaseFee@tx: {summary['baseFeeAtTxGwei']:.2f} Gwei)")

    print(f"💰 Total Fee: {summary['totalFeeEth']:.6f} ETH")
      if args.warn_fee_eth > 0 and summary["totalFeeEth"] > args.warn_fee_eth:
        print(f"⚠️  High Fee Warning: {summary['totalFeeEth']:.4f} ETH exceeds threshold {args.warn_fee_eth:.4f} ETH.")


    print(f"⏱️  Elapsed: {time.time() - t0:.2f}s")

if __name__ == "__main__":
    main()
