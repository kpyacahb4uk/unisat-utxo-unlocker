from colorama import Fore, Style
import sys
import time

def display_menu():
    print(f"\n{Fore.CYAN}Select mode:{Style.RESET_ALL}")
    print(f"{Fore.WHITE}[1] Check UTXO only (no transactions) {Fore.GREEN}<-- USE IT for first time!{Style.RESET_ALL}")
    print(f"{Fore.WHITE}[2] Process and send to destination{Style.RESET_ALL}")
    print(f"{Fore.WHITE}[0] Exit{Style.RESET_ALL}\n")

    try:
        choice = input(f"{Fore.YELLOW}Enter choice [1]: {Style.RESET_ALL}").strip()

        if choice == '':
            return 1
        elif choice == '0':
            return 0
        elif choice == '1':
            return 1
        elif choice == '2':
            return 2
        else:
            print(f"{Fore.RED}Invalid choice, using default mode 1{Style.RESET_ALL}")
            return 1
    except KeyboardInterrupt:
        return 0

def get_user_choice():
    return display_menu()
