import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Style
from datetime import datetime
from .wallet import BitcoinWallet
from .utils import get_fee_rate, format_satoshi, load_seeds, load_destinations, save_failed_wallets, get_btc_price
from .proxy_manager import ProxyManager

class WalletTask:
    def __init__(self, wallet, destination, task_id):
        self.wallet = wallet
        self.destination = destination
        self.task_id = task_id
        self.merge_tx = None
        self.final_tx = None
        self.status = "pending"
        self.utxos = []
        self.total_value = 0

class BatchProcessor:
    def __init__(self, seeds_file, destination_file, workers=10, batch_size=10, check_interval=30, fee_multiplier=1.1, check_only=False, filter_tasks=None):
        self.seeds_file = seeds_file
        self.destination_file = destination_file

        if filter_tasks:
            # Use only filtered tasks (wallets with UTXO from previous check)
            self.seeds = [task.wallet.seed_phrase for task in filter_tasks]
        else:
            self.seeds = load_seeds(seeds_file)

        self.destination = load_destinations(destination_file)[0]  # Single destination
        self.workers = workers
        self.batch_size = batch_size
        self.check_interval = check_interval
        self.fee_multiplier = fee_multiplier
        self.check_only = check_only
        self.tasks = []
        self.completed = 0
        self.failed = 0
        self.btc_price = None
        self.proxy_manager = ProxyManager()
    
    def log(self, wallet_id, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": Fore.WHITE,
            "SUCCESS": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "TX": Fore.CYAN
        }
        color = colors.get(level, Fore.WHITE)
        prefix = f"[{timestamp}] [{Fore.BLUE}W{wallet_id:03d}{Style.RESET_ALL}]"
        print(f"{prefix} {color}{message}{Style.RESET_ALL}")
    
    def process_wallet(self, task):
        try:
            wallet = task.wallet
            destination = task.destination
            wallet_id = task.task_id

            utxos = wallet.get_utxos()

            if not utxos:
                self.log(wallet_id, "No UTXO found", "WARNING")
                task.status = "empty"
                return True

            total = sum(u['value'] for u in utxos)
            task.utxos = utxos
            task.total_value = total

            self.log(wallet_id, f"Found {len(utxos)} UTXO, total: {format_satoshi(total)}", "SUCCESS")

            # If check_only mode, just mark as completed and return
            if self.check_only:
                task.status = "checked"
                return True

            if len(utxos) == 1:
                self.log(wallet_id, "Already merged, sending to destination", "INFO")
                fee_rate = get_fee_rate(self.fee_multiplier)
                tx = wallet.create_transaction(utxos, destination, fee_rate)
                
                if tx:
                    tx_id = wallet.broadcast_transaction(tx)
                    if tx_id:
                        task.final_tx = tx_id
                        task.status = "completed"
                        self.log(wallet_id, f"Transaction: {tx_id}", "TX")
                        self.completed += 1
                        return True
                    else:
                        self.log(wallet_id, "Broadcast failed", "ERROR")
                        task.status = "failed"
                        self.failed += 1
                        return False
            
            self.log(wallet_id, f"Merging {len(utxos)} UTXO", "INFO")
            fee_rate = get_fee_rate(self.fee_multiplier)
            merge_tx = wallet.create_transaction(utxos, wallet.address, fee_rate)
            
            if merge_tx:
                merge_id = wallet.broadcast_transaction(merge_tx)
                if merge_id:
                    task.merge_tx = merge_id
                    task.status = "merging"
                    self.log(wallet_id, f"Merge TX: {merge_id}", "TX")
                    return True
                else:
                    self.log(wallet_id, "Merge broadcast failed", "ERROR")
                    task.status = "failed"
                    self.failed += 1
                    return False
            
            self.log(wallet_id, "Transaction creation failed", "ERROR")
            task.status = "failed"
            self.failed += 1
            return False
            
        except Exception as e:
            self.log(task.task_id, f"Error: {str(e)}", "ERROR")
            task.status = "failed"
            self.failed += 1
            return False
    
    def finalize_wallet(self, task):
        try:
            wallet = task.wallet
            destination = task.destination
            wallet_id = task.task_id
            
            if wallet.check_confirmation(task.merge_tx):
                self.log(wallet_id, "Merge confirmed, sending to destination", "SUCCESS")
                
                time.sleep(2)
                new_utxos = wallet.get_utxos()
                
                if new_utxos:
                    fee_rate = get_fee_rate(self.fee_multiplier)
                    final_tx = wallet.create_transaction(new_utxos, destination, fee_rate)
                    
                    if final_tx:
                        final_id = wallet.broadcast_transaction(final_tx)
                        if final_id:
                            task.final_tx = final_id
                            task.status = "completed"
                            self.log(wallet_id, f"Final TX: {final_id}", "TX")
                            self.completed += 1
                            return True
                
                self.log(wallet_id, "Final transaction failed", "ERROR")
                task.status = "failed"
                self.failed += 1
                return False
            
            return None
            
        except Exception as e:
            self.log(wallet_id, f"Finalize error: {str(e)}", "ERROR")
            task.status = "failed"
            self.failed += 1
            return False
    
    def run(self):
        print(f"\n{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Starting {'UTXO check' if self.check_only else 'processing'}{Style.RESET_ALL}")
        print(f"Mode: {Fore.YELLOW}{'Check only' if self.check_only else 'Process and send'}{Style.RESET_ALL}")
        print(f"Wallets: {len(self.seeds)}")
        print(f"{Fore.GREEN}{'='*50}{Style.RESET_ALL}\n")

        # Fetch BTC price if in check mode
        if self.check_only:
            print(f"{Fore.CYAN}Fetching BTC price...{Style.RESET_ALL}")
            self.btc_price = get_btc_price()
            if self.btc_price:
                print(f"{Fore.GREEN}BTC Price: ${self.btc_price:,.2f}{Style.RESET_ALL}\n")
            else:
                print(f"{Fore.YELLOW}Could not fetch BTC price{Style.RESET_ALL}\n")

        start_time = time.time()

        for i, seed in enumerate(self.seeds):
            proxy = self.proxy_manager.get_proxy(wallet_id=i + 1)
            wallet = BitcoinWallet(seed, i + 1, proxy=proxy)
            task = WalletTask(wallet, self.destination, i + 1)
            self.tasks.append(task)
        
        batches = [self.tasks[i:i + self.batch_size] for i in range(0, len(self.tasks), self.batch_size)]

        for batch_num, batch in enumerate(batches, 1):
            print(f"\n{Fore.YELLOW}{'Checking' if self.check_only else 'Processing'} batch {batch_num}/{len(batches)}{Style.RESET_ALL}")

            with ThreadPoolExecutor(max_workers=min(self.workers, len(batch))) as executor:
                executor.map(self.process_wallet, batch)

        # Skip merging if check_only mode
        if self.check_only:
            merging_tasks = []
        else:
            merging_tasks = [t for t in self.tasks if t.status == "merging"]
        
        if merging_tasks:
            print(f"\n{Fore.YELLOW}Waiting for {len(merging_tasks)} merge confirmations{Style.RESET_ALL}")
            
            while merging_tasks:
                time.sleep(self.check_interval)
                
                for task in merging_tasks[:]:
                    result = self.finalize_wallet(task)
                    if result is not None:
                        merging_tasks.remove(task)
                
                if merging_tasks:
                    print(f"{Fore.YELLOW}Still waiting for {len(merging_tasks)} confirmations...{Style.RESET_ALL}")
        
        elapsed = int(time.time() - start_time)

        print(f"\n{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'Check' if self.check_only else 'Processing'} complete{Style.RESET_ALL}")

        if self.check_only:
            checked_with_utxo = [t for t in self.tasks if t.status == 'checked']
            print(f"With UTXO: {Fore.GREEN}{len(checked_with_utxo)}{Style.RESET_ALL}")
            print(f"Empty: {Fore.YELLOW}{len([t for t in self.tasks if t.status == 'empty'])}{Style.RESET_ALL}")
            print(f"Failed: {Fore.RED}{self.failed}{Style.RESET_ALL}")
        else:
            print(f"Successful: {Fore.GREEN}{self.completed}{Style.RESET_ALL}")
            print(f"Failed: {Fore.RED}{self.failed}{Style.RESET_ALL}")
            print(f"Empty: {Fore.YELLOW}{len([t for t in self.tasks if t.status == 'empty'])}{Style.RESET_ALL}")

        print(f"Time: {elapsed//60}m {elapsed%60}s")

        # Show wallets with UTXO in check mode
        if self.check_only:
            checked_with_utxo = [t for t in self.tasks if t.status == 'checked']
            if checked_with_utxo:
                print(f"\n{Fore.GREEN}Wallets with UTXO:{Style.RESET_ALL}")
                total_btc = 0
                total_usd = 0

                for task in checked_with_utxo:
                    btc_value = task.total_value / 100000000
                    total_btc += btc_value

                    print(f"  {Fore.GREEN}[W{task.task_id:03d}]{Style.RESET_ALL} {task.wallet.address}")
                    print(f"        UTXO count: {len(task.utxos)}")
                    print(f"        Value: {btc_value:.8f} BTC", end="")

                    if self.btc_price:
                        usd_value = btc_value * self.btc_price
                        total_usd += usd_value
                        print(f" (${usd_value:,.2f})")
                    else:
                        print()

                # Show total
                print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}TOTAL:{Style.RESET_ALL}")
                print(f"  Wallets: {Fore.GREEN}{len(checked_with_utxo)}{Style.RESET_ALL}")
                print(f"  BTC: {Fore.GREEN}{total_btc:.8f}{Style.RESET_ALL}")
                if self.btc_price:
                    print(f"  USD: {Fore.GREEN}${total_usd:,.2f}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")

        # Show and save failed tasks
        failed_tasks = [t for t in self.tasks if t.status == 'failed']
        if failed_tasks:
            print(f"\n{Fore.RED}Failed Wallets:{Style.RESET_ALL}")
            for task in failed_tasks:
                print(f"  {Fore.RED}[W{task.task_id:03d}]{Style.RESET_ALL} {task.wallet.address}")
                if task.total_value > 0:
                    print(f"        Value: {format_satoshi(task.total_value)}")

            failed_file = save_failed_wallets(failed_tasks)
            print(f"\n{Fore.YELLOW}Failed wallets saved to: {failed_file}{Style.RESET_ALL}")

        print(f"{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
