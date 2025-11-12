import time, csv, argparse, sys
from web3 import Web3

def check_endpoint(rpc_url, threshold_ms=200):
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout":10}))
    if not w3.is_connected():
        return rpc_url, None, None, "DISCONNECTED"
    t0 = time.time()
    block = w3.eth.block_number
    latency_ms = (time.time() - t0) * 1000
    print(f"✅ RPC {rpc_url} latency: {latency_ms:.0f} ms (timeout: {w3.provider._provider_request_kwargs.get('timeout', 'n/a')} s)")
    status = "OK" if latency_ms <= threshold_ms else "SLOW"
    return rpc_url, block, round(latency_ms), status

def main():
    parser = argparse.ArgumentParser(description="RPC latency monitor")
    parser.add_argument("--rpcs", nargs="+", required=True, help="List of RPC URLs")
    parser.add_argument("--threshold", type=int, default=200, help="Latency threshold in ms")
    parser.add_argument("--output", default="rpc_latency_log.csv", help="Output log file path")
    args = parser.parse_args()

    # Run once (could be looped or scheduled)
    results = []
    for url in args.rpcs:
        url, block, latency, status = check_endpoint(url, args.threshold)
        results.append((time.strftime("%Y-%m-%d %H:%M:%S"), url, block, latency, status))

    with open(args.output, "a", newline="") as f:
        writer = csv.writer(f)
        for row in results:
            writer.writerow(row)
            print(row)

if __name__ == "__main__":
    main()
