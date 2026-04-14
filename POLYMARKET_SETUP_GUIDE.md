# How to Set Up Polymarket Live Betting

## Step 1: Create a Polygon wallet
- Install MetaMask browser extension
- Create a new wallet (save the seed phrase securely offline)
- Switch network to Polygon (Matic) in MetaMask

## Step 2: Fund with USDC
- Buy USDC on Coinbase or Binance
- Withdraw to your Polygon wallet address
- Start with $50-100 USDC for testing

## Step 3: Get your private key
- In MetaMask: Account Details > Export Private Key
- Enter your MetaMask password
- Copy the private key (starts with 0x...)
- NEVER share this key with anyone

## Step 4: Add to VPS
SSH into the VPS and add to .env:
POLYMARKET_PRIVATE_KEY=0x<your_private_key>

## Step 5: Install CLOB client
pip install py-clob-client

## Step 6: Test connection
python3 /root/limitless-ai/test_polymarket.py

## Step 7: Switch to live mode
In run_paper_trade.py, change: dry_run=True to dry_run=False

DO THIS ONLY AFTER BACKTESTING SHOWS WIN RATE > 55% over 30+ decisions.