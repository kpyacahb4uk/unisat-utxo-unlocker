from bitcoinutils.hdwallet import HDWallet
from bitcoinutils.keys import PrivateKey
from bitcoinutils.setup import setup
from bitcoinutils.transactions import TxInput, TxOutput, Transaction, TxWitnessInput
import requests
import time

setup("mainnet")

class BitcoinWallet:
    def __init__(self, seed_phrase, wallet_id, proxy=None):
        self.wallet_id = wallet_id
        self.seed_phrase = seed_phrase
        self.proxy = proxy
        hdw = HDWallet(mnemonic=seed_phrase)
        hdw.from_path("m/86'/0'/0'/0/0")
        self.private_key_wif = hdw.get_private_key().to_wif()
        self.wif_private_key = PrivateKey.from_wif(self.private_key_wif)
        self.public_key = self.wif_private_key.get_public_key()
        self.address = self.public_key.get_taproot_address().to_string()
    
    def get_utxos(self):
        all_utxos = []

        try:
            response = requests.get(
                f"https://mempool.space/api/address/{self.address}/utxo",
                timeout=10,
                proxies=self.proxy
            )
            if response.status_code == 200:
                for utxo in response.json():
                    if utxo.get('status', {}).get('confirmed'):
                        all_utxos.append({
                            'txid': utxo['txid'],
                            'vout': utxo['vout'],
                            'value': utxo['value']
                        })
            
            response = requests.get(
                f"https://mempool.space/api/address/{self.address}/txs",
                timeout=10,
                proxies=self.proxy
            )
            if response.status_code == 200:
                for tx in response.json()[:20]:
                    for vout_idx, output in enumerate(tx['vout']):
                        if output.get('scriptpubkey_address') == self.address:
                            txid = tx['txid']
                            vout = vout_idx
                            
                            if not any(u['txid'] == txid and u['vout'] == vout for u in all_utxos):
                                try:
                                    spent_resp = requests.get(
                                        f"https://mempool.space/api/tx/{txid}/outspend/{vout}",
                                        timeout=5,
                                        proxies=self.proxy
                                    )
                                    if spent_resp.status_code == 200:
                                        if not spent_resp.json().get('spent'):
                                            all_utxos.append({
                                                'txid': txid,
                                                'vout': vout,
                                                'value': output['value']
                                            })
                                except:
                                    pass
        except:
            pass
        
        seen = set()
        unique = []
        for u in all_utxos:
            key = f"{u['txid']}:{u['vout']}"
            if key not in seen:
                seen.add(key)
                unique.append(u)
        
        return sorted(unique, key=lambda x: x['value'], reverse=True)
    
    def create_transaction(self, utxos, to_address, fee_rate):
        if not utxos:
            return None
        
        total = sum(u['value'] for u in utxos)
        num_inputs = len(utxos)
        tx_size = int((10.5 + (57.5 * num_inputs) + 43) * 1.02)
        fee = int(tx_size * fee_rate)
        output_amount = total - fee
        
        if output_amount < 546:
            return None
        
        from_address = self.public_key.get_taproot_address()
        
        if to_address == self.address:
            to_addr_obj = from_address
        else:
            from bitcoinutils.keys import P2trAddress
            to_addr_obj = P2trAddress.from_address(to_address)
        
        tx_in = [TxInput(u['txid'], u['vout']) for u in utxos]
        tx_out = TxOutput(output_amount, to_addr_obj.to_script_pub_key())
        tx = Transaction(tx_in, [tx_out], has_segwit=True)
        
        amounts = [u['value'] for u in utxos]
        pubkeys = [from_address.to_script_pub_key() for _ in utxos]

        # Collect all signatures first
        signatures = []
        for i in range(num_inputs):
            sig = self.wif_private_key.sign_taproot_input(
                tx, i, pubkeys, amounts, script_path=False, tapleaf_scripts=[]
            )
            signatures.append(sig)

        # Add all witnesses after all signatures are collected
        for sig in signatures:
            tx.witnesses.append(TxWitnessInput([sig]))

        return tx.serialize()
    
    def broadcast_transaction(self, signed_tx):
        try:
            response = requests.post(
                "https://blockstream.info/api/tx",
                data=signed_tx,
                timeout=10,
                proxies=self.proxy
            )
            if response.status_code == 200:
                return response.text.strip()
        except:
            pass
        return None
    
    def check_confirmation(self, tx_id):
        try:
            response = requests.get(
                f"https://mempool.space/api/tx/{tx_id}/status",
                timeout=10,
                proxies=self.proxy
            )
            if response.status_code == 200:
                return response.json().get('confirmed', False)
        except:
            pass
        return False
