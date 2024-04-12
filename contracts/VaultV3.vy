# @version 0.3.10

"""
@title Zharta Renting Vault Contract
@author [Zharta](https://zharta.io/)
@notice This contract is the vault implementation for the LOTM Renting Protocol.
@dev This is the implementation contract for each vault, which is deployed as a minimal proxy (ERC1167) by `RentingV3.vy` and accepts only calls from it. This contract holds the assets (NFTs) ) but does not store any information regarding the token, so pre-conditions must be validated by the caller (`RentingV3.vy`). It implement the functions required for token delegation and staking.
Delegations are performed by warm.xyz HotWalletProxy.
"""

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721

interface IDelegationRegistry:
    def getHotWallet(cold_wallet: address) -> address: view
    def setHotWallet(hot_wallet_address: address, expiration_timestamp: uint256, lock_hot_wallet_address: bool): nonpayable
    def setExpirationTimestamp(expiration_timestamp: uint256): nonpayable


# Structs

struct SingleNft:
    tokenId: uint32
    amount: uint224


# Global Variables

caller: public(address)
payment_token: public(immutable(IERC20))
nft_contract: public(immutable(IERC721))
delegation_registry: public(immutable(IDelegationRegistry))


##### EXTERNAL METHODS - WRITE #####

@payable
@external
def __init__(
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address,
):

    """
    @dev Sets up the contract by initializing the payment token, NFT contract, delegation registry and staking contract addresses.
    @param _payment_token_addr The address of the payment token contract.
    @param _nft_contract_addr The address of the NFT contract.
    @param _delegation_registry_addr The address of the delegation registry contract.
    """

    assert _payment_token_addr != empty(address), "payment token addr not set"
    assert _nft_contract_addr != empty(address), "nft contract addr not set"
    assert _delegation_registry_addr != empty(address), "delegation addr not set"

    payment_token = IERC20(_payment_token_addr)
    nft_contract = IERC721(_nft_contract_addr)
    delegation_registry = IDelegationRegistry(_delegation_registry_addr)


# Functions

@external
def initialise():

    """
    @notice Initialize a vault contract, setting the caller as the contract deployer.
    @dev Ensures that the vault is not already initialized.
    """

    assert self.caller == empty(address), "already initialised"
    self.caller = msg.sender


@external
def deposit(token_id: uint256, nft_owner: address, delegate: address):

    """
    @notice Deposit an NFT into the vault and optionaly sets up delegation.
    @dev Transfers the NFT from the owner to the vault and optionally sets up delegation.
    @param token_id The id of the NFT to be deposited.
    @param nft_owner The address of the NFT owner.
    @param delegate The address to delegate the NFT to. If empty no delegation is done.
    """

    assert msg.sender == self.caller, "not caller"

    nft_contract.safeTransferFrom(nft_owner, self, token_id, b"")

    if delegate != empty(address):
        self._delegate_to_wallet(delegate, max_value(uint256))


@external
def withdraw(token_id: uint256, wallet: address):

    """
    @notice Withdraw an NFT from the vault and transfer it to the wallet.
    @dev Transfers the NFT from the vault to the wallet and clears the delegation.
    @param token_id The id of the NFT to be withdrawn.
    @param wallet The address of the wallet to receive the NFT.
    """

    assert msg.sender == self.caller, "not caller"
    nft_contract.safeTransferFrom(self, wallet, token_id, b"")
    self._delegate_to_wallet(empty(address), 0)


@external
def delegate_to_wallet(delegate: address, expiration: uint256):

    """
    @notice Delegate the NFT to a wallet.
    @dev Delegates the NFT to the given address.
    @param delegate The address to delegate the NFT to.
    @param expiration The expiration timestamp for the delegation.
    """

    assert msg.sender == self.caller, "not caller"
    self._delegate_to_wallet(delegate, expiration)


@external
def staking_deposit(sender: address, amount: uint256, token_id: uint256, staking_addr: address, pool_method_id: bytes4):

    """
    @notice Deposit the payment token into the staking contract.
    @dev Deposits the payment token into the staking contract.
    @param sender The address of the payment token sender.
    @param amount The amount of the payment token to deposit.
    @param token_id The id of the NFT supporting the deposit, which must be deposited in the vault.
    @param staking_addr The address of the staking contract.
    @param pool_method_id The method id of the staking pool deposit function.
    """

    assert msg.sender == self.caller, "not caller"
    self._staking_deposit(sender, amount, token_id, staking_addr, pool_method_id)


@external
def staking_withdraw(wallet: address, amount: uint256, token_id: uint256, staking_addr: address, pool_method_id: bytes4):

    """
    @notice Withdraw the payment token from the staking contract.
    @dev Withdraws the payment token from the staking contract.
    @param wallet The address of the wallet to receive the payment token.
    @param amount The amount of the payment token to withdraw.
    @param token_id The id of the NFT supporting the withdrawal, which must be deposited in the vault.
    @param staking_addr The address of the staking contract.
    @param pool_method_id The method id of the staking pool withdraw function.
    """

    assert msg.sender == self.caller, "not caller"
    self._staking_withdraw(wallet, amount, token_id, staking_addr, pool_method_id)


@external
def staking_claim(wallet: address, token_id: uint256, staking_addr: address, pool_method_id: bytes4):

    """
    @notice Claim the staking rewards.
    @dev Claims the staking rewards.
    @param wallet The address of the wallet to receive the staking rewards.
    @param token_id The id of the NFT supporting the claim, which must be deposited in the vault.
    @param staking_addr The address of the staking contract.
    @param pool_method_id The method id of the staking pool claim function.
    """
    assert msg.sender == self.caller, "not caller"
    self._staking_claim(wallet, token_id, staking_addr, pool_method_id)


@external
def staking_compound(token_id: uint256, staking_addr: address, pool_claim_method_id: bytes4, pool_deposit_method_id: bytes4):

    """
    @notice Compound the staking rewards.
    @dev Compounds the staking rewards by claiming and depositing them. No validations are performed regarding staking limits or minimal deposit amounts.
    @param token_id The id of the NFT supporting the compound, which must be deposited in the vault.
    @param staking_addr The address of the staking contract.
    @param pool_claim_method_id The method id of the staking pool claim function.
    @param pool_deposit_method_id The method id of the staking pool deposit function.
    """

    assert msg.sender == self.caller, "not caller"
    self._staking_claim(self, token_id, staking_addr, pool_claim_method_id)
    self._staking_deposit(self, payment_token.balanceOf(self), token_id, staking_addr, pool_deposit_method_id)


@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:

    """
    @notice ERC721 token receiver callback.
    @dev Returns the ERC721 receiver callback selector.
    @param _operator The address which called `safeTransferFrom` function.
    @param _from The address which previously owned the token.
    @param _tokenId The NFT identifier which is being transferred.
    @param _data Additional data with no specified format.
    @return The ERC721 receiver callback selector.
    """

    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)


@internal
def _delegate_to_wallet(delegate: address, expiration: uint256):
    if delegation_registry.getHotWallet(self) == delegate:
        delegation_registry.setExpirationTimestamp(expiration)
    else:
        delegation_registry.setHotWallet(delegate, expiration, False)


@internal
def _staking_deposit(wallet: address, amount: uint256, token_id: uint256, staking_addr: address, pool_method_id: bytes4):
    payment_token.approve(staking_addr, amount)

    nfts: DynArray[SingleNft, 1] = [SingleNft({tokenId: convert(token_id, uint32), amount: convert(amount, uint224)})]
    raw_call(staking_addr, concat(pool_method_id, _abi_encode(nfts)))


@internal
def _staking_withdraw(wallet: address, amount: uint256, token_id: uint256, staking_addr: address, pool_method_id: bytes4):

    nfts: DynArray[SingleNft, 1] = [SingleNft({tokenId: convert(token_id, uint32), amount: convert(amount, uint224)})]
    raw_call(staking_addr, concat(pool_method_id, _abi_encode(nfts, wallet)))


@internal
def _staking_claim(wallet: address, token_id: uint256, staking_addr: address, pool_method_id: bytes4):

    nfts: DynArray[uint256, 1] = [token_id]
    raw_call(staking_addr, concat(pool_method_id, _abi_encode(nfts, wallet)))
