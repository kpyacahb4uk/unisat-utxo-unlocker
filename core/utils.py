import json
import requests
from pathlib import Path
from colorama import Fore, Style
from datetime import datetime

def ensure_data_folder():
    data_path = Path("data")
    if not data_path.exists():
        data_path.mkdir()
    return data_path

def load_config():
    config_path = Path("config.json")
    
    if not config_path.exists():
        default_config = {
            "seeds_file": "data/seeds.txt",
            "destination_file": "data/destination.txt",
            "max_workers": 10,
            "batch_size": 10,
            "check_interval": 30,
            "fee_multiplier": 1.1
        }
        
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        ensure_data_folder()
        return default_config
    
    with open(config_path, 'r') as f:
        config = json.load(f)
        ensure_data_folder()
        return config

def load_seeds(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Seeds file not found: {filepath}")
    
    with open(path, 'r') as f:
        seeds = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    if not seeds:
        raise ValueError("No seeds found in file")
    
    return seeds

def load_destinations(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Destination file not found: {filepath}")
    
    with open(path, 'r') as f:
        destinations = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    if not destinations:
        raise ValueError("No destination found in file")
    
    return destinations

def validate_files(seeds_file, destination_file):
    try:
        seeds = load_seeds(seeds_file)
        destinations = load_destinations(destination_file)

        print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Found {len(seeds)} seed phrases")
        print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Destination address loaded")

        return True

    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {str(e)}")
        return False

def get_btc_price():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        if response.status_code == 200:
            price = response.json().get('bitcoin', {}).get('usd')
            if price:
                return float(price)
    except:
        pass

    try:
        response = requests.get("https://mempool.space/api/v1/prices", timeout=5)
        if response.status_code == 200:
            price = response.json().get('USD')
            if price:
                return float(price)
    except:
        pass

    return None

def get_fee_rate(multiplier=1.1):
    try:
        response = requests.get("https://mempool.space/api/v1/fees/recommended", timeout=5)
        if response.status_code == 200:
            fees = response.json()
            min_fee = fees.get('minimumFee', 1)
            return round(min_fee * multiplier, 1)
    except:
        pass
    return 1.5

def format_satoshi(sats):
    if sats >= 100000000:
        return f"{sats/100000000:.8f} BTC"
    elif sats >= 1000000:
        return f"{sats:,} sats ({sats/100000000:.6f} BTC)"
    else:
        return f"{sats:,} sats"

def save_failed_wallets(failed_tasks):
    if not failed_tasks:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/failed_wallets_{timestamp}.txt"

    ensure_data_folder()

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Failed Wallets Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        f.write(f"Total failed wallets: {len(failed_tasks)}\n\n")
        f.write("="*60 + "\n\n")

        for task in failed_tasks:
            f.write(f"Wallet ID: {task.task_id}\n")
            f.write(f"Address: {task.wallet.address}\n")
            f.write(f"Destination: {task.destination}\n")
            f.write(f"Status: {task.status}\n")
            if task.merge_tx:
                f.write(f"Merge TX: {task.merge_tx}\n")
            if task.utxos:
                f.write(f"UTXOs count: {len(task.utxos)}\n")
                f.write(f"Total value: {format_satoshi(task.total_value)}\n")
                for idx, utxo in enumerate(task.utxos, 1):
                    f.write(f"  UTXO {idx}: {utxo['txid']}:{utxo['vout']} - {format_satoshi(utxo['value'])}\n")
            f.write("-"*60 + "\n\n")

    return filename
