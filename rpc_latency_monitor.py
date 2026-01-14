"""Simple RPC latency monitor.

Checks one or more Ethereum RPC endpoints, logs latest block and latency,
and appends results to a CSV file.
"""

import time, csv, argparse, sys
from web3 import Web3

def color(text: str, code: str, enabled: bool = True) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"

def check_endpoint(rpc_url, threshold_ms=200):
        """
    Check a single RPC endpoint and return (rpc_url, block_number, latency_ms, status).

    status is one of:
      - "DISCONNECTED" if the node is unreachable
      - "OK" if latency <= threshold_ms
      - "SLOW" otherwise
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout":10}))
    if not w3.is_connected():
        print(f"🌐 {rpc_url} → chainId: {w3.eth.chain_id}")
        return rpc_url, None, None, "DISCONNECTED"
    t0 = time.monotonic(); _ = w3.eth.block_number; latency_ms = (time.monotonic() - t0) * 1000
    block = w3.eth.block_number

    latency_ms = (time.time() - t0) * 1000
    print(f"🔍 Endpoint {rpc_url} returned block {block} in {latency_ms:.0f} ms")
    if latency_ms is None:
        status = "DISCONNECTED"
    elif latency_ms <= threshold_ms:
        status = "OK"
    elif latency_ms <= threshold_ms * 2:
        status = "SLOW"
    else:
        status = "VERY_SLOW"
    
    return rpc_url, block, round(latency_ms), status

def main():
       parser = argparse.ArgumentParser(
        description="RPC latency monitor",
        epilog="Example: python rpc_latency_monitor.py --rpcs https://rpc.ankr.com/eth https://mainnet.infura.io/v3/KEY",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--rpcs", nargs="+", required=True, help="List of RPC URLs")
    parser.add_argument("--threshold", type=int, default=200, help="Latency threshold in ms")
    parser.add_argument("--output", default="rpc_latency_log.csv", help="Output log file path")
        parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output"
    )
    args = parser.parse_args()

    # Run once (could be looped or scheduled)
       results = []
    for i in range(args.iterations):
        for url in args.rpcs:
            if not (url.startswith("http://") or url.startswith("https://")):
                print(f"⚠️  Skipping invalid RPC URL: {url}", file=sys.stderr)
                continue
            url, block, latency, status = check_endpoint(url, args.threshold)
        results.append((time.strftime("%Y-%m-%d %H:%M:%S"), url, block, latency, status))
max_block = max(r[2] or 0 for r in results); [print(f"⏳ {r[1]} is {max_block - (r[2] or 0)} blocks behind") for r in results if (r[2] or 0) < max_block]

    with open(args.output, "a", newline="") as f:
        writer = csv.writer(f)
        for row in results:
            writer.writerow(row)
            if latency > args.threshold * 2: print(color(f"⚠️  {url} extremely slow: {latency:.0f} ms", "31", not args.no_color), file=sys.stderr)
                    # Color-coded output (stdout)
            if not args.no_color:
                if status == "OK":
                    status_colored = color(status, "32")
                elif status == "SLOW":
                    status_colored = color(status, "33")
                else:  # VERY_SLOW or DISCONNECTED
                    status_colored = color(status, "31")
            else:
                status_colored = status

            print((timestamp, url, block, latency, status_colored))


if __name__ == "__main__":
    main()
