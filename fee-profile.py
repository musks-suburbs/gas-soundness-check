"""Profile recent gas behavior on an EVM network.

Samples recent blocks and computes percentiles for base fee, effective gas price,
and priority tip (approx.) in Gwei.
"""

# Example:
#   python fee_profile.py --rpc https://mainnet.infura.io/v3/YOUR_KEY \
#       --blocks 300 --step 3 --json

import os
import sys
import time
import argparse
import json
from typing import Dict, List, Tuple, Optional

from statistics import median
from web3 import Web3



DEFAULT_RPC = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/your_api_key")
DEFAULT_BLOCKS = int(os.getenv("FEE_PROFILE_BLOCKS", "300"))
DEFAULT_STEP = int(os.getenv("FEE_PROFILE_STEP", "3"))

NETWORKS = {
    1: "Ethereum Mainnet",
    11155111: "Sepolia Testnet",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum One",
}

def network_name(cid: int) -> str:
    """Map a chain ID to a human-readable network name (or a fallback string)."""
    return NETWORKS.get(cid, f"Unknown (chain ID {cid})")

def connect(rpc: str) -> Web3:
    """Connect to an RPC endpoint and print a short banner."""
    start = time.time()
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        print(f"❌ Failed to connect to RPC endpoint: {rpc}", file=sys.stderr)
        sys.exit(1)
    latest = w3.eth.block_number
    latency = time.time() - start
    print(f"🌐 chainId={w3.eth.chain_id} tip={latest}", file=sys.stderr)
    print(f"⚡ RPC connected in {latency:.2f}s", file=sys.stderr)
    return w3




def pct(values: List[float], q: float) -> float:
    """Return the q-th percentile (0..1) of a list of floats."""
    if not values:
        return 0.0
    q = max(0.0, min(1.0, q))
    sorted_vals = sorted(values)
    idx = int(round(q * (len(sorted_vals) - 1)))
    return sorted_vals[idx]



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

def analyze(
    w3: Web3,
    blocks: int,
    step: int,
    head_override: Optional[int] = None,
) -> Dict[str, object]:
    head = int(head_override) if head_override is not None else int(w3.eth.block_number)
    start = max(0, head - blocks + 1)
    t0 = time.time()

    basefees: List[float] = []
    eff_prices: List[float] = []
    tips: List[float] = []

    print(f"🔍 Scanning the last {blocks} blocks (every {step}th block)...", file=sys.stderr)

    # Iterate backwards in steps for speed
    for n in range(head, start - 1, -step):
        blk = w3.eth.get_block(n, full_transactions=True)
        bf = int(getattr(blk, "baseFeePerGas", getattr(blk, "base_fee_per_gas", 0) or 0))

        basefees.append(float(Web3.from_wei(bf, "gwei")))
        eff_gwei, tip_gwei = sample_block_fees(blk, bf)
        eff_prices.extend(eff_gwei)
        tips.extend(tip_gwei)

        # Show progress every 20 sampled blocks
        if len(basefees) % 20 == 0:
            print(f"🔍 Sampled {len(basefees)} blocks so far (latest={n})", file=sys.stderr)

    elapsed = time.time() - t0

    # Estimate average block time
    if len(basefees) >= 2 and head > start:
        first_block = w3.eth.get_block(head)
        last_block = w3.eth.get_block(start)
        avg_gas = sum(tx.gasPrice for tx in w3.eth.get_block(block.number, True).transactions if hasattr(tx, "gasPrice")) / max(1, len(block.transactions)); print(f"⛽ Avg gas price in block: {w3.from_wei(int(avg_gas), 'gwei'):.2f} Gwei")
        time_diff = first_block.timestamp - last_block.timestamp
        block_time_avg = max(0.0, time_diff / (head - start))
    else:
        block_time_avg = 0.0

    zero_tip_count = sum(1 for x in tips if x == 0.0)

    return {
        "chainId": int(w3.eth.chain_id),
        "network": network_name(int(w3.eth.chain_id)),
        "avgBlockTimeSec": round(block_time_avg, 2),
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
            "countZero": zero_tip_count,
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Profile recent gas: base fee, effective price, and priority tip percentiles.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--rpc", default=DEFAULT_RPC, help="RPC URL (default from RPC_URL env)")
    ap.add_argument(
        "-b",
        "--blocks",
        type=int,
        default=DEFAULT_BLOCKS,
        help="How many recent blocks to scan",
    )
    ap.add_argument(
        "-s",
        "--step",
        type=int,
        default=DEFAULT_STEP,
        help="Sample every Nth block for speed",
    )
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    ap.add_argument(
        "--head",
        type=int,
        help="Use this block number as the head instead of the latest",
    )
    return ap.parse_args()



def main() -> None:
    args = parse_args()
        print(f"📅 Fee-Profile run started at UTC: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}")
    print(f"⚙️ Using RPC endpoint: {args.rpc}")
        if args.blocks <= 0 or args.step <= 0:
        print("❌ --blocks and --step must be > 0", file=sys.stderr)
                if args.blocks > 100_000:
        print("⚠️  --blocks is very large; this may take a long time.", file=sys.stderr)
        sys.exit(1)
        # ✅ Prevent huge block scans that could overload the RPC
    if args.blocks > 5000:
        print("⚠️  Limiting --blocks to 5000 to avoid excessive RPC load.")
        args.blocks = 5000


          w3 = connect(args.rpc)
    result = analyze(w3, args.blocks, args.step, args.head)
    if result["sampledBlocks"] == 0:
        print("⚠️  No blocks were sampled. Check --blocks/--step and head range.", file=sys.stderr)

      if args.json:
        payload = {
            "mode": "fee_profile",
            "network": result["network"],
            "chainId": result["chainId"],
            "generatedAtUtc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "data": result,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return


    print(f"🌐 {result['network']} (chainId {result['chainId']})  head={result['head']}")
    print(f"📦 Scanned ~{result['sampledBlocks']} blocks over last {result['blockSpan']} (step={result['step']}) in {result['timingSec']}s") 
    bf = result["baseFeeGwei"]
    ep = result["effectivePriceGwei"]
    tp = result["tipGweiApprox"]
    print(f"📊 Sampled transactions: effective={ep['count']}  tip={tp['count']}")
    print(f"🕒 Average Block Time: {result['avgBlockTimeSec']} seconds")
    print(f"🎯 Gas target ratio: {(block.gasUsed / (block.gasLimit / 2)) * 100:.1f}% of target")
    print(f"⛽ Base Fee (Gwei):   p50={bf['p50']}  p95={bf['p95']}  min={bf['min']}  max={bf['max']}")
    print(f"💵 Effective Price:   p50={ep['p50']}  p95={ep['p95']}  min={ep['min']}  max={ep['max']}  (n={ep['count']})")
        print(
        f"🎁 Priority Tip ~:    p50={tp['p50']}  p95={tp['p95']}  min={tp['min']}  max={tp['max']}  "
        f"(n={tp['count']}, zero={tp.get('countZero', 0)})"
    )

    # New: show share of zero-tip transactions
    if tp["count"] > 0:
        zero_tip_pct = tp.get("countZero", 0) / tp["count"] * 100.0
        print(f"🎯 Zero-tip share: {zero_tip_pct:.1f}% of sampled txs")

    print("ℹ️  Tip for EIP-1559 uses tx.maxPriorityFeePerGas; legacy approximates tip = gasPrice - baseFee.")

    print(f"\n🕒 Completed at: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC")

if __name__ == "__main__":
    # CLI entrypoint
    main()

