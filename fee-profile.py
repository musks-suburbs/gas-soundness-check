# fee_profile.py
import os
import sys
import time
import argparse
from statistics import median
from typing import Dict, List, Tuple
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

def connect(rpc: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        print("❌ Failed to connect to RPC.")
        sys.exit(1)
    return w3

def pct(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    idx = max(0, min(len(values)-1, int(round(q * (len(values)-1)))))
    return sorted(values)[idx]

def sample_block_fees(block, base_fee_wei: int) -> Tuple[List[float], List[float]]:
    """
    Returns (effective_prices_gwei, tip_gwei_approx) for txs in the block.
    Approximation:
      - EIP-1559: effective ~= min(maxFeePerGas, baseFee + maxPriorityFeePerGas)
                  tip ~= maxPriorityFeePerGas
      - Legacy:   effective = gasPrice
                  tip ~= max(0, gasPrice - baseFee)
    """
    eff = []
    tip = []
    bf = base_fee_wei or 0
    for tx in block.transactions:
        # EIP-1559 type can be 2, AccessList 1, Legacy 0/None
        ttype = tx.get("type", 0) if isinstance(tx, dict) else getattr(tx, "type", 0)
        if ttype == 2:  # EIP-1559
            mpp = int(tx.get("maxPriorityFeePerGas", 0))
            mfp = int(tx.get("maxFeePerGas", 0))
            effective = min(mfp, bf + mpp)
            eff.append(float(Web3.from_wei(effective, "gwei")))
            tip.append(float(Web3.from_wei(mpp, "gwei")))
        else:
            gp = int(tx.get("gasPrice", 0))
            eff.append(float(Web3.from_wei(gp, "gwei")))
            tip.append(float(Web3.from_wei(max(0, gp - bf), "gwei")))
    return eff, tip

def analyze(w3: Web3, blocks: int, step: int) -> Dict:
    head = int(w3.eth.block_number)
    start = max(0, head - blocks + 1)
    t0 = time.time()
    basefees, eff_prices, tips = [], [], []

    # Iterate backwards in steps for speed
    for n in range(head, start - 1, -step):
        blk = w3.eth.get_block(n, full_transactions=True)
        bf = int(blk.get("baseFeePerGas", 0))
        basefees.append(float(Web3.from_wei(bf, "gwei")))
        eff_gwei, tip_gwei = sample_block_fees(blk, bf)
        eff_prices.extend(eff_gwei)
        tips.extend(tip_gwei)

    elapsed = time.time() - t0
    return {
        "chainId": int(w3.eth.chain_id),
        "network": network_name(int(w3.eth.chain_id)),
        "head": head,
        "sampledBlocks": len(range(head, start - 1, -step)),
        "blockSpan": blocks,
        "step": step,
        "timingSec": round(elapsed, 2),
        "baseFeeGwei": {
            "p50": round(median(basefees), 3) if basefees else 0.0,
            "p95": round(pct(basefees, 0.95), 3) if basefees else 0.0,
            "min": round(min(basefees), 3) if basefees else 0.0,
            "max": round(max(basefees), 3) if basefees else 0.0,
        },
        "effectivePriceGwei": {
            "p50": round(median(eff_prices), 3) if eff_prices else 0.0,
            "p95": round(pct(eff_prices, 0.95), 3) if eff_prices else 0.0,
            "min": round(min(eff_prices), 3) if eff_prices else 0.0,
            "max": round(max(eff_prices), 3) if eff_prices else 0.0,
            "count": len(eff_prices),
        },
        "tipGweiApprox": {
            "p50": round(median(tips), 3) if tips else 0.0,
            "p95": round(pct(tips, 0.95), 3) if tips else 0.0,
            "min": round(min(tips), 3) if tips else 0.0,
            "max": round(max(tips), 3) if tips else 0.0,
            "count": len(tips),
        },
    }

def parse_args():
    ap = argparse.ArgumentParser(
        description="Profile recent gas: base fee, effective price, and priority tip percentiles."
    )
    ap.add_argument("--rpc", default=DEFAULT_RPC, help="RPC URL (default from RPC_URL env)")
    ap.add_argument("--blocks", type=int, default=300, help="How many recent blocks to scan (default 300)")
    ap.add_argument("--step", type=int, default=3, help="Sample every Nth block for speed (default 3)")
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    return ap.parse_args()

def main():
    args = parse_args()
    if args.blocks <= 0 or args.step <= 0:
        print("❌ --blocks and --step must be > 0")
        sys.exit(1)

    w3 = connect(args.rpc)
    result = analyze(w3, args.blocks, args.step)
    import time
print(f"⏱️ Analysis completed in {round(time.time() - t0, 2)} seconds.")


    if args.json:
        import json
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    print(f"🌐 {result['network']} (chainId {result['chainId']})  head={result['head']}")
    print(f"📦 Scanned ~{result['sampledBlocks']} blocks over last {result['blockSpan']} (step={result['step']}) in {result['timingSec']}s")
    bf = result["baseFeeGwei"]
    ep = result["effectivePriceGwei"]
    tp = result["tipGweiApprox"]
    print(f"⛽ Base Fee (Gwei):   p50={bf['p50']}  p95={bf['p95']}  min={bf['min']}  max={bf['max']}")
    print(f"💵 Effective Price:   p50={ep['p50']}  p95={ep['p95']}  min={ep['min']}  max={ep['max']}  (n={ep['count']})")
    print(f"🎁 Priority Tip ~:    p50={tp['p50']}  p95={tp['p95']}  min={tp['min']}  max={tp['max']}  (n={tp['count']})")
    print("ℹ️  Tip for EIP-1559 uses tx.maxPriorityFeePerGas; legacy approximates tip = gasPrice - baseFee.")

if __name__ == "__main__":
    main()
