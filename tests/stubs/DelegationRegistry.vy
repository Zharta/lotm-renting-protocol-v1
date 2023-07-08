event HotWalletChanged:
    coldWallet: address
    _from: address
    to: address
    expirationTimestamp: uint256


@external
def setHotWallet(hot_wallet_address: address, expiration_timestamp: uint256, lock_hot_wallet_address: bool):
    pass


@external
def setExpirationTimestamp(expiration_timestamp: uint256):
    pass

@external
def renounceHotWallet():
    pass


@view
@external
def getHotWallet(cold_wallet: address) -> address:
    return empty(address)
