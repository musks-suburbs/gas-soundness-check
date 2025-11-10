# README.md
# gas-soundness-check

## Overview
This repository contains a small Python script that checks the **soundness of transaction gas usage** on Ethereum or any EVM-compatible chain.  
It connects to an RPC endpoint, fetches live gas metrics, retrieves a transaction receipt, and reports detailed gas and fee information.

## Features
- Connects to Ethereum or testnets
- Prints transaction sender, recipient, and block info
- Displays gas used, total ETH fee, and fee warnings
- Fetches live base fee and suggested gas price
- Simple and portable — one file, minimal dependencies

## Installation
1. Install Python 3.10 or higher.
2. Install dependency:
   ```bash
   pip install web3
3. Set up an RPC endpoint (optional):
'export RPC_URL="https://mainnet.infura.io/v3/<YOUR_KEY>"'

## Usage

Run the script with a transaction hash:
'python app.py 0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'

Optionally specify an RPC:
'python app.py 0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --rpc https://rpc.ankr.com/eth'

## Example Output
- 🌐 Connected to Ethereum Mainnet (chainId 1)
- 🔗 Transaction: 0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- 👤 From: 0x742d35Cc6634C0532925a3b844Bc454e4438f44e
- 🎯 To: 0x00000000219ab540356cBB839Cbe05303d7705Fa
- 📦 Status: ✅ Success
- 🔢 Block: 18945023
- ⛽ Gas Used: 64231
- 💰 Fee: 0.001562 ETH
- 📊 Network Gas Info:
- 🧱 Current Block: 18945025
- 🕒 Block Time: 2025-11-09 14:41:22 UTC
- ⛽ Base Fee: 25.40 Gwei
- ⚙️  Suggested Gas Price: 27.12 Gwei
- ⏱️  Elapsed: 2.35s
