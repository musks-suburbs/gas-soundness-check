# app.py
import os
import sys
import time
import argparse
from web3 import Web3

# Default RPC configuration
RPC_URL = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/your_api_key")

NETWORKS = {
    1: "Ethereum Mainnet",
    11155111: "Sepolia Testnet",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum One",
}

def network_name(chain_id: int) -> str:
    return NETWORKS.get(chain_id, f"Unknown (chain ID {chain_id})")

def connect(rpc: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        print("❌ Failed to connect to RPC endpoint.")
        sys.exit(1)
    return w3

def parse_hash(value: str) -> str:
    if not (value.startswith("0x") and len(value) == 66):
        print("❌ Invalid transaction hash. Expected 0x + 64 hex characters.")
        sys.exit(1)
    return value

def fetch_gas_data(w3: Web3, block_tag="latest"):
    block = w3.eth.get_block(block_tag)
    base_fee = block.get("baseFeePerGas", 0)
    gas_price = w3.eth.gas_price
    return {
        "block_number": block.number,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(block.timestamp)),
        "base_fee_gwei": Web3.from_wei(base_fee, 'gwei'),
        "gas_price_gwei": Web3.from_wei(gas_price, 'gwei'),
    }

def fetch_tx_data(w3: Web3, tx_hash: str):
    rcpt = w3.eth.get_transaction_receipt(tx_hash)
    tx = w3.eth.get_transaction(tx_hash)
    fee = Web3.from_wei(rcpt.gasUsed * tx.get("maxFeePerGas", tx.gasPrice), "ether")
    return {
        "from": tx["from"],
        "to": tx["to"],
        "status": rcpt.status,
        "gas_used": rcpt.gasUsed,
        "fee_eth": float(fee),
        "block_number": rcpt.blockNumber,
    }

def main():
    parser = argparse.ArgumentParser(description="Check Ethereum transaction gas soundness.")
    parser.add_argument("tx_hash", help="Transaction hash (0x...)")
    parser.add_argument("--rpc", default=RPC_URL, help="RPC endpoint (default from RPC_URL env)")
    args = parser.parse_args()

   w3 = connect(args.rpc)
print(f"✔️  Connected to {network_name(w3.eth.chain_id)} (chainId {w3.eth.chain_id}) — proceeding…")
print(f"🧱 Current block number: {w3.eth.block_number}")


    tx_hash = parse_hash(args.tx_hash)
    start = time.time()

    gas_data = fetch_gas_data(w3)
    tx_data = fetch_tx_data(w3, tx_hash)

    print("\n🔗 Transaction:", tx_hash)
    print(f"👤 From: {tx_data['from']}")
    print(f"🎯 To: {tx_data['to']}")
    print(f"📦 Status: {'✅ Success' if tx_data['status'] == 1 else '❌ Failed'}")
    print(f"🔢 Block: {tx_data['block_number']}")
    print(f"⛽ Gas Used: {tx_data['gas_used']}")
    print(f"💰 Fee: {tx_data['fee_eth']:.6f} ETH")

    if tx_data["fee_eth"] > 0.05:
        print(f"⚠️  High Fee Warning: This transaction cost {tx_data['fee_eth']:.4f} ETH.")

    print("\n📊 Network Gas Info:")
    print(f"🧱 Current Block: {gas_data['block_number']}")
    print(f"🕒 Block Time: {gas_data['timestamp']} UTC")
    print(f"⛽ Base Fee: {gas_data['base_fee_gwei']:.2f} Gwei")
    print(f"⚙️  Suggested Gas Price: {gas_data['gas_price_gwei']:.2f} Gwei")

    print(f"\n⏱️  Elapsed: {time.time() - start:.2f}s")

if __name__ == "__main__":
    main()
