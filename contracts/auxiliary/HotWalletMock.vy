# @version 0.3.9

##
## Quick mock of [HotWalletProxy](https://etherscan.io/address/0xf4fbf314e8819a8d4d496bfb3cdcd3687d0bbcb8#code#F1#L51)
## TODO add the remaining functions
##


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
