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

STAKING_DEPOSIT_METHOD: constant(bytes4[3]) = [
    method_id("depositApeCoin(uint256,address)", output_type=bytes4),
    method_id("depositBAYC((uint32,uint224)[])", output_type=bytes4),
    method_id("depositMAYC((uint32,uint224)[])", output_type=bytes4),
]

STAKING_WITHDRAW_METHOD: constant(bytes4[3]) = [
    method_id("withdrawApeCoin(uint256,address)", output_type=bytes4),
    method_id("withdrawBAYC((uint32,uint224)[],address)", output_type=bytes4),
    method_id("withdrawMAYC((uint32,uint224)[],address)", output_type=bytes4),
]

STAKING_CLAIM_METHOD: constant(bytes4[3]) = [
    method_id("claimApeCoin(address)", output_type=bytes4),
    method_id("claimBAYC(uint256[],address)", output_type=bytes4),
    method_id("claimMAYC(uint256[],address)", output_type=bytes4),
]

nft_owner: public(address)
token_id: public(uint256)
payment_token_addr: public(immutable(address))
nft_contract_addr: public(immutable(address))
delegation_registry_addr: public(immutable(address))
staking_addr: public(immutable(address))
staking_pool_id: public(immutable(uint256))


##### EXTERNAL METHODS - WRITE #####

@payable
@external
def __init__(
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address,
    _staking_addr: address,
    _staking_pool_id: uint256,
):

    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    delegation_registry_addr = _delegation_registry_addr
    staking_addr = _staking_addr
    staking_pool_id = _staking_pool_id


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
def delegate_to_wallet(delegate: address, expiration: uint256):
    pass

@view
@external
def is_initialised() -> bool:
    return False

@external
def staking_deposit(sender: address, amount: uint256):
    pass

@external
def staking_withdraw(sender: address, amount: uint256):
    pass

@external
def staking_claim(sender: address, amount: uint256):
    pass

@external
def staking_compound(sender: address):
    pass
