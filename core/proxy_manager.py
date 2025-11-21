import random
from pathlib import Path
from colorama import Fore, Style

class ProxyManager:
    def __init__(self, proxy_file="data/proxies.txt"):
        self.proxy_file = proxy_file
        self.proxies = []
        self.current_index = 0
        self.load_proxies()

    def load_proxies(self):
        """Load proxies from file"""
        proxy_path = Path(self.proxy_file)

        if not proxy_path.exists():
            print(f"{Fore.YELLOW}No proxy file found at {self.proxy_file}. Running without proxies.{Style.RESET_ALL}")
            return

        with open(proxy_path, 'r') as f:
            raw_proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        # Parse proxies in format: protocol://ip:port or ip:port or user:pass@ip:port
        for proxy_str in raw_proxies:
            try:
                # If no protocol specified, assume http
                if '://' not in proxy_str:
                    proxy_str = f'http://{proxy_str}'

                self.proxies.append({
                    'http': proxy_str,
                    'https': proxy_str
                })
            except Exception as e:
                print(f"{Fore.RED}Invalid proxy format: {proxy_str}{Style.RESET_ALL}")

        if self.proxies:
            print(f"{Fore.GREEN}Loaded {len(self.proxies)} proxies{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No valid proxies found. Running without proxies.{Style.RESET_ALL}")

    def get_proxy(self, wallet_id=None):
        """Get next proxy in rotation"""
        if not self.proxies:
            return None

        if wallet_id is not None:
            # Assign proxy based on wallet_id for consistency
            proxy_index = (wallet_id - 1) % len(self.proxies)
        else:
            # Round-robin rotation
            proxy_index = self.current_index
            self.current_index = (self.current_index + 1) % len(self.proxies)

        return self.proxies[proxy_index]

    def get_random_proxy(self):
        """Get random proxy"""
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def count(self):
        """Return number of loaded proxies"""
        return len(self.proxies)
