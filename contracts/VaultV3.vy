# @version 0.3.9

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721

interface IDelegationRegistry:
    def getHotWallet(cold_wallet: address) -> address: view
    def setHotWallet(hot_wallet_address: address, expiration_timestamp: uint256, lock_hot_wallet_address: bool): nonpayable
    def setExpirationTimestamp(expiration_timestamp: uint256): nonpayable

interface IStaking:
    def depositApeCoin(amount: uint256, recipient: address): nonpayable
    def depositBAYC(nfts: DynArray[SingleNft,1]): nonpayable
    def depositMAYC(nfts: DynArray[SingleNft,1]): nonpayable
    def withdrawApeCoin(amount: uint256, recipient: address): nonpayable
    def withdrawBAYC(nfts: DynArray[SingleNft,1], recipient: address): nonpayable
    def withdrawMAYC(nfts: DynArray[SingleNft,1], recipient: address): nonpayable
    def claimApeCoin(recipient: address): nonpayable
    def claimBAYC(nfts: DynArray[uint256,1], recipient: address): nonpayable
    def claimMAYC(nfts: DynArray[uint256,1], recipient: address): nonpayable


# Structs

struct SingleNft:
    tokenId: uint32
    amount: uint224


# Global Variables

MAX_STAKE_POOL_ID: constant(uint256) = 2

STAKING_DEPOSIT_METHOD: constant(bytes4[3]) = [0xbd5023a9, 0x46583a05, 0x8ecbffa7]
# depositApeCoin(uint256,address), depositBAYC((uint32,uint224)[]), depositMAYC((uint32,uint224)[])

STAKING_WITHDRAW_METHOD: constant(bytes4[3]) = [0xe4e81847, 0xaceb3629, 0xed23c906]
# withdrawApeCoin(uint256,address), withdrawBAYC((uint32,uint224)[],address), withdrawMAYC((uint32,uint224)[],address)

STAKING_CLAIM_METHOD: constant(bytes4[3]) = [0x2ee2de66, 0xb682e859, 0x57a26300]
# claimApeCoin(address), claimBAYC(uint256[],address), claimMAYC(uint256[],address)

caller: public(address)
nft_owner: public(address)
token_id: public(uint256)
payment_token: public(immutable(IERC20))
nft_contract: public(immutable(IERC721))
delegation_registry: public(immutable(IDelegationRegistry))
staking_addr: public(immutable(address))
staking_pool_id: public(uint256)



##### EXTERNAL METHODS - WRITE #####

@payable
@external
def __init__(
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address,
    _staking_addr: address,
):

    payment_token = IERC20(_payment_token_addr)
    nft_contract = IERC721(_nft_contract_addr)
    delegation_registry = IDelegationRegistry(_delegation_registry_addr)
    staking_addr = _staking_addr


# Functions

@external
def initialise(token_id: uint256, nft_owner: address, staking_pool_id: uint256):
    assert not self._is_initialised(), "already initialised"
    assert staking_pool_id <= MAX_STAKE_POOL_ID, "invalid staking pool id"

    if self.caller != empty(address):
        assert msg.sender == self.caller, "not caller"
    else:
        self.caller = msg.sender

    self.token_id = token_id
    self.nft_owner = nft_owner
    self.staking_pool_id = staking_pool_id


@external
def deposit(delegate: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"

    nft_contract.safeTransferFrom(self.nft_owner, self, self.token_id, b"")

    if delegate != empty(address):
        self._delegate_to_wallet(delegate, 0)


@external
def withdraw(sender: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    nft_contract.safeTransferFrom(self, sender, self.token_id, b"")
    self.nft_owner = empty(address)

@external
def delegate_to_wallet(delegate: address, expiration: uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    self._delegate_to_wallet(delegate, expiration)


@external
def staking_deposit(sender: address, amount: uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert payment_token.allowance(sender, self) >= amount, "insufficient allowance"

    assert payment_token.transferFrom(sender, self, amount), "transferFrom failed"
    self._staking_deposit(sender, amount)



@external
def staking_withdraw(wallet: address, amount: uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    self._staking_withdraw(wallet, amount)


@external
def staking_claim(wallet: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    self._staking_claim(wallet)

@external
def staking_compound(wallet: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    self._staking_claim(self)
    self._staking_deposit(wallet, payment_token.balanceOf(self))


@view
@external
def is_initialised() -> bool:
    return self._is_initialised()


@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)


@internal
def _delegate_to_wallet(delegate: address, expiration: uint256):
    if delegation_registry.getHotWallet(self) == delegate:
        delegation_registry.setExpirationTimestamp(expiration)
    else:
        delegation_registry.setHotWallet(delegate, expiration, False)


@internal
def _staking_deposit(wallet: address, amount: uint256):
    payment_token.approve(staking_addr, amount)

    if self.staking_pool_id == 0:
        raw_call(
            staking_addr,
            _abi_encode(STAKING_DEPOSIT_METHOD[self.staking_pool_id], self.token_id, self)
        )
    else:
        nfts: DynArray[SingleNft, 1] = [
            SingleNft({tokenId: convert(self.token_id, uint32), amount: convert(amount, uint224)})
        ]

        raw_call(
            staking_addr,
            _abi_encode(STAKING_DEPOSIT_METHOD[self.staking_pool_id], nfts)
        )


@internal
def _staking_withdraw(wallet: address, amount: uint256):
    payment_token.approve(staking_addr, amount)

    if self.staking_pool_id == 0:
        raw_call(
            staking_addr,
            _abi_encode(STAKING_WITHDRAW_METHOD[self.staking_pool_id], self.token_id, wallet)
        )
    else:
        nfts: DynArray[SingleNft, 1] = [
            SingleNft({tokenId: convert(self.token_id, uint32), amount: convert(amount, uint224)})
        ]

        raw_call(
            staking_addr,
            _abi_encode(STAKING_WITHDRAW_METHOD[self.staking_pool_id], nfts, wallet)
        )


@internal
def _staking_claim(wallet: address):

    if self.staking_pool_id == 0:
        raw_call(
            staking_addr,
            _abi_encode(STAKING_CLAIM_METHOD[self.staking_pool_id], self.token_id, wallet)
        )
    else:
        nfts: DynArray[uint256, 1] = [self.token_id]
        raw_call(
            staking_addr,
            _abi_encode(STAKING_CLAIM_METHOD[self.staking_pool_id], nfts, wallet)
        )


@view
@internal
def _is_initialised() -> bool:
    return self.nft_owner != empty(address)
