import os
import sys
from algosdk import account, transaction
from algosdk.v2client import algod
from algosdk import mnemonic

def main():
    payer_private_key = os.getenv('PAYER_PRIVATE_KEY')
    if not payer_private_key:
        print('Error: PAYER_PRIVATE_KEY environment variable not set.', file=sys.stderr)
        sys.exit(1)
    # Derive address
    try:
        payer_address = account.address_from_private_key(payer_private_key)
    except Exception as e:
        print(f'Error deriving address: {e}', file=sys.stderr)
        sys.exit(1)
    # Verify address matches expected
    expected_address = 'J6ZWTKW2OBBN5CSEHWCZSDZNYBSYDTTZ3FIJFQSTR4HOXWC4T46EMREDTY'
    if payer_address != expected_address:
        print(f'Warning: derived address {payer_address} does not match expected {expected_address}', file=sys.stderr)
    # Algorand TestNet node parameters (configurable)
    algod_address = os.getenv('ALGOD_ADDRESS', 'https://testnet-algorand.api.purestake.io/ps2')
    algod_token = os.getenv('ALGOD_TOKEN', '')
    headers = {}
    # If using PureStake endpoint, require API key header
    if 'purestake' in algod_address.lower():
        api_key = os.getenv('PURESTAKE_API_KEY')
        if not api_key:
            print('Error: PURESTAKE_API_KEY not set for PureStake endpoint.', file=sys.stderr)
            sys.exit(1)
        headers['X-API-Key'] = api_key
    client = algod.AlgodClient(algod_token, algod_address, headers)
    # Check opt-in status
    asset_id = 10458941
    account_info = client.account_info(payer_address)
    holding = next((holding for holding in account_info.get('assets', []) if holding['asset-id'] == asset_id), None)
    if holding:
        print('Already opted in to ASA 10458941.')
        return
    # Get transaction params
    params = client.suggested_params()
    # Create opt-in transaction (asset transfer of 0 to self)
    txn = transaction.AssetTransferTxn(
        sender=payer_address,
        sp=params,
        receiver=payer_address,
        amt=0,
        index=asset_id
    )
    signed_txn = txn.sign(payer_private_key)
    try:
        txid = client.send_transaction(signed_txn)
        print(f'Transaction ID: {txid}')
        # Wait for confirmation
        confirmed_txn = transaction.wait_for_confirmation(client, txid, 5)
        print('Transaction confirmed.')
    except Exception as e:
        print(f'Error sending transaction: {e}', file=sys.stderr)
        sys.exit(1)
    # Verify opt-in again
    account_info = client.account_info(payer_address)
    holding = next((h for h in account_info.get('assets', []) if h['asset-id'] == asset_id), None)
    if holding:
        print('Opt-in successful.')
    else:
        print('Opt-in failed.')

if __name__ == '__main__':
    main()

