"""
@title Quick mock of warm.xyz HotWalletProxy
@notice This impementation is for test purposes ONLY and IS NOT part of the protocol
@dev Implementation of basic mock functionality for mock of [HotWalletProxy](https://etherscan.io/address/0xf4fbf314e8819a8d4d496bfb3cdcd3687d0bbcb8#code#F1#L51)
"""

# @version 0.3.10

## TODO add the remaining functions

struct WalletLink:
    walletAddress: address
    expirationTimestamp: uint256

event HotWalletChanged:
    coldWallet: address
    _from: address
    to: address
    expirationTimestamp: uint256


hot: HashMap[address, address]
exp: HashMap[address, uint256]

@external
def setHotWallet(hot_wallet_address: address, expiration_timestamp: uint256, lock_hot_wallet_address: bool):
    old_hot_wallet: address = self.hot[msg.sender]
    self.hot[msg.sender] = hot_wallet_address
    self.exp[msg.sender] = expiration_timestamp if hot_wallet_address != empty(address) else 0
    log HotWalletChanged(msg.sender, old_hot_wallet, hot_wallet_address, expiration_timestamp)

@external
def setExpirationTimestamp(expiration_timestamp: uint256):
    self.exp[msg.sender] = expiration_timestamp

@view
@external
def getHotWallet(cold_wallet: address) -> address:
    return self.hot[cold_wallet] if self.exp[cold_wallet] > block.timestamp else empty(address)

@view
@external
def getHotWalletLink(cold_wallet: address) -> WalletLink:
    return WalletLink({
        walletAddress: self.hot[cold_wallet] if self.exp[cold_wallet] > block.timestamp else empty(address),
        expirationTimestamp: self.exp[cold_wallet]
    })

@view
@external
def getColdWalletLinks(hot_wallet: address) -> DynArray[WalletLink, 128]:
    return []
