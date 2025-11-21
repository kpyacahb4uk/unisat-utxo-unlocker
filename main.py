#!/usr/bin/env python3

import os
import sys
import time
from pathlib import Path
from colorama import init, Fore, Style
from core.processor import BatchProcessor
from core.utils import load_config, validate_files
from core.menu import display_menu

init(autoreset=True)

def print_banner():
    banner = f"""
{Fore.CYAN}─────▄───▄
─▄█▄─█▀█▀█─▄█▄
▀▀████▄█▄████▀▀
─────▀█▀█▀{Style.RESET_ALL}

{Fore.YELLOW}UNISAT UTXO UNLOCKER{Style.RESET_ALL}
{Fore.WHITE}t.me/alreadydead{Style.RESET_ALL}
    """
    print(banner)

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()

    # Check for command line flags
    auto_mode = '--auto' in sys.argv or '-y' in sys.argv
    check_mode = '--check' in sys.argv or '-c' in sys.argv

    if check_mode:
        print(f"\n{Fore.CYAN}Check mode enabled{Style.RESET_ALL}")
        mode = 1
    elif auto_mode:
        print(f"\n{Fore.GREEN}Auto mode enabled, starting immediately...{Style.RESET_ALL}")
        mode = 2
    else:
        mode = display_menu()

    if mode == 0:
        print(f"\n{Fore.RED}Exiting...{Style.RESET_ALL}")
        sys.exit(0)

    print(f"\n{Fore.GREEN}Loading configuration...{Style.RESET_ALL}")

    try:
        config = load_config()
        seeds_file = config['seeds_file']
        destination_file = config['destination_file']

        if not validate_files(seeds_file, destination_file):
            print(f"{Fore.RED}File validation failed{Style.RESET_ALL}")
            sys.exit(1)

        wallets_with_utxo = None

        # Mode 1: Check only
        if mode == 1:
            processor = BatchProcessor(
                seeds_file=seeds_file,
                destination_file=destination_file,
                workers=config['max_workers'],
                batch_size=config['batch_size'],
                check_interval=config['check_interval'],
                fee_multiplier=config['fee_multiplier'],
                check_only=True
            )

            processor.run()

            # Get wallets with UTXO
            wallets_with_utxo = [t for t in processor.tasks if t.status == 'checked']

            if not wallets_with_utxo:
                print(f"\n{Fore.YELLOW}No wallets with UTXO found. Exiting.{Style.RESET_ALL}")
                sys.exit(0)

            # Ask user if they want to process wallets with UTXO (only in interactive mode)
            if not check_mode:
                print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Found {len(wallets_with_utxo)} wallet(s) with UTXO{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Do you want to process them now?{Style.RESET_ALL}")
                print(f"{Fore.WHITE}[1] Yes, process and send to destination{Style.RESET_ALL}")
                print(f"{Fore.WHITE}[0] No, exit{Style.RESET_ALL}\n")

                try:
                    choice = input(f"{Fore.YELLOW}Enter choice [0]: {Style.RESET_ALL}").strip()
                    if choice != '1':
                        print(f"\n{Fore.YELLOW}Exiting without processing.{Style.RESET_ALL}")
                        sys.exit(0)
                except (KeyboardInterrupt, EOFError):
                    print(f"\n{Fore.YELLOW}Exiting...{Style.RESET_ALL}")
                    sys.exit(0)
            else:
                # In --check mode, just exit after showing results
                print(f"\n{Fore.GREEN}Check complete. Use mode [2] to process wallets.{Style.RESET_ALL}")
                sys.exit(0)

            # User wants to process
            print(f"\n{Fore.GREEN}Starting processing of {len(wallets_with_utxo)} wallet(s)...{Style.RESET_ALL}")
            mode = 2

        # Mode 2: Process and send
        if mode == 2:
            processor = BatchProcessor(
                seeds_file=seeds_file,
                destination_file=destination_file,
                workers=config['max_workers'],
                batch_size=config['batch_size'],
                check_interval=config['check_interval'],
                fee_multiplier=config['fee_multiplier'],
                check_only=False,
                filter_tasks=wallets_with_utxo
            )

            processor.run()

    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Process interrupted by user{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Fatal error: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == "__main__":
    main()
