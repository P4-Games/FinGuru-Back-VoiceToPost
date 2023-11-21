from algosdk import account, encoding
from algosdk.v2client import algod
import algosdk
from fastapi import HTTPException, Response
# generate an account
private_key, address = account.generate_account()

private_key = algosdk.mnemonic.to_private_key("supreme protect marriage little siren brief pull remember plunge outside deposit tomato drink coyote boy romance fee empower scatter green token february clog ability glance")
address = account.address_from_private_key(private_key)
#print("Private key:", private_key)
print("Address:", address)

algod_address = "https://testnet-api.algonode.cloud"
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

created_asset = 0

def create_token():
    sp = algod_client.suggested_params()
    txn = algosdk.transaction.AssetConfigTxn(
        sender=address,
        sp=sp,
        default_frozen=False,
        unit_name="NewsCoin",
        asset_name="News Coin",
        manager=address,
        reserve=address,
        freeze=address,
        clawback=address,
        #url="https://path/to/my/asset/details",
        total=1000000,
        decimals=18,
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
    sp = algod_client.suggested_params()
    """
    xopfer_txn = algosdk.transaction.AssetOptInTxn(
        sender = address, 
        index = 477809769,
        sp=sp
    )

    signed_xfer_txn = xopfer_txn.sign(private_key)
    txid = algod_client.send_transaction(signed_xfer_txn)
    print(f"Sent transfer transaction with txid: {txid}")

    results = algosdk.transaction.wait_for_confirmation(algod_client, txid, 4)
    """
    # Create transfer transaction
    xfer_txn = algosdk.transaction.AssetTransferTxn(
        sender=address,
        sp=sp,
        receiver=address_to_send,
        amt=amount,
        index=475348419,
    )
    signed_xfer_txn = xfer_txn.sign(private_key)
    try:
        txid = algod_client.send_transaction(signed_xfer_txn)
    except algosdk.error.AlgodHTTPError as e:
        return Response(content="Error al enviar los tokens", status_code=404)
    print(f"Sent transfer transaction with txid: {txid}")

    results = algosdk.transaction.wait_for_confirmation(algod_client, txid, 4)
    return (f"Result confirmed in tx: {txid}")

#transfer_tokens("XJ6LZLT4MU3H7PYAXL54PBLJ4FSXVJVUQ4IC26MV4CR73MF6W5W7WPV434", 1)