import time, csv, argparse, sys
from web3 import Web3

def check_endpoint(rpc_url, threshold_ms=200):
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout":10}))
    if not w3.is_connected():
        print(f"🌐 {rpc_url} → chainId: {w3.eth.chain_id}")
        return rpc_url, None, None, "DISCONNECTED"
    t0 = time.time()
    block = w3.eth.block_number
    if 'last_block' in locals() and block == last_block: print(f"⚠️  {rpc_url} hasn’t advanced since last check (block {block})")
    last_block = block
    latency_ms = (time.time() - t0) * 1000
    print(f"🔍 Endpoint {rpc_url} returned block {block} in {latency_ms:.0f} ms")
    status = "OK" if latency_ms <= threshold_ms else "SLOW"
    
    return rpc_url, block, round(latency_ms), status

def main():
    parser = argparse.ArgumentParser(description="RPC latency monitor")
    parser.add_argument("--rpcs", nargs="+", required=True, help="List of RPC URLs")
    parser.add_argument("--threshold", type=int, default=200, help="Latency threshold in ms")
    parser.add_argument("--output", default="rpc_latency_log.csv", help="Output log file path")
        parser.add_argument(
        "--max-latency-exit",
        type=int,
        help="If set, exit with code 1 if any endpoint latency (ms) exceeds this value",
    )
    args = parser.parse_args()

    # Run once (could be looped or scheduled)
    results = []
    for url in args.rpcs:
        url, block, latency, status = check_endpoint(url, args.threshold)
        results.append((time.strftime("%Y-%m-%d %H:%M:%S"), url, block, latency, status))
    if args.max_latency_exit is not None:
        too_slow = any(
            latency is not None and latency > args.max_latency_exit
            for _, _, _, latency, _ in results
        )
        if too_slow:
            print(
                f"⚠️  At least one endpoint exceeded max latency of {args.max_latency_exit} ms",
                file=sys.stderr,
            )
            # still write CSV, but remember to exit with 1 at the very end
            exit_code = 1
        else:
            exit_code = 0
    else:
        exit_code = 0

    with open(args.output, "a", newline="") as f:
        writer = csv.writer(f)
        for row in results:
            writer.writerow(row)
            if latency > args.threshold * 2: print(f"⚠️  {url} extremely slow: {latency:.0f} ms")
            print(row)

if __name__ == "__main__":
    main()
    sys.exit(exit_code)
