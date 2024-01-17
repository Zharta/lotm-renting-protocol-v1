# @version 0.3.9

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721

interface IDelegationRegistry:
    def getHotWallet(cold_wallet: address) -> address: view
    def setHotWallet(hot_wallet_address: address, expiration_timestamp: uint256, lock_hot_wallet_address: bool): nonpayable
    def setExpirationTimestamp(expiration_timestamp: uint256): nonpayable


# Structs

# Global Variables

nft_owner: public(address)
token_id: public(uint256)
payment_token_addr: public(immutable(address))
nft_contract_addr: public(immutable(address))
delegation_registry_addr: public(immutable(address))


##### EXTERNAL METHODS - WRITE #####

@payable
@external
def __init__(
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address,
    _registry_addr: address
):

    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    delegation_registry_addr = _delegation_registry_addr
    registry_addr = _registry_addr




# Functions

@external
def initialise(token_id: uint256, owner: address):
    pass

@external
def deposit(delegate: address):
    pass

@external
def withdraw(sender: address):
    pass

@external
def delegate_to_wallet(sender: address, delegate: address, expiration: uint256):
    pass

@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
    pass

@view
@external
def is_initialised() -> bool:
    pass

@view
@external
def owner() -> address:
    pass


@view
@external
def payment_token_addr() -> address:
    pass

@view
@external
def nft_contract_addr() -> address:
    pass

@view
@external
def delegation_registry_addr() -> address:
    pass
