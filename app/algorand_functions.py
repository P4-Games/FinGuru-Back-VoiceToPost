from algosdk import account, encoding
from algosdk.v2client import algod
import algosdk
# generate an account
private_key, address = account.generate_account()
print("Private key:", private_key)
print("Address:", address)

algod_address = "http://localhost:4001"
algod_token = "a" * 64
algod_client = algod.AlgodClient(algod_token, algod_address)

# Or, if necessary, pass alternate headers

# Create a new client with an alternate api key header
special_algod_client = algod.AlgodClient(
    "", algod_address, headers={"X-API-Key": algod_token}
)

from typing import Dict, Any

account_info: Dict[str, Any] = algod_client.account_info(address)
print(f"Account balance: {account_info.get('amount')} microAlgos")


def create_token():
    sp = algod_client.suggested_params()
    txn = algosdk.transaction.AssetConfigTxn(
        sender=address,
        sp=sp,
        default_frozen=False,
        unit_name="rug",
        asset_name="Really Useful Gift",
        manager=address,
        reserve=address,
        freeze=address,
        clawback=address,
        url="https://path/to/my/asset/details",
        total=1000,
        decimals=0,
    )

    # Sign with secret key of creator
    stxn = txn.sign(private_key)
    # Send the transaction to the network and retrieve the txid.
    txid = algod_client.send_transaction(stxn)
    print(f"Sent asset create transaction with txid: {txid}")
    # Wait for the transaction to be confirmed
    results = algosdk.transaction.wait_for_confirmation(algod_client, txid, 4)
    print(f"Result confirmed in round: {results['confirmed-round']}")

    # grab the asset id for the asset we just created
    created_asset = results["asset-index"]
    print(f"Asset ID created: {created_asset}")

def transfer_tokens(address_to_send, amount):
    pass