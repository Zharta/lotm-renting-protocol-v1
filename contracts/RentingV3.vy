# @version 0.3.9

# Interfaces

interface ISelf:
    def tokenid_to_vault(token_id: uint256) -> address: view
    def is_vault_available(token_id: uint256) -> bool: view


interface IVault:
    def is_initialised() -> bool: view
    def initialise(owner: address): nonpayable
    def deposit(token_id: uint256, delegate: address): nonpayable
    def withdraw(sender: address) -> (uint256, uint256): nonpayable
    def delegate_to_wallet(sender: address, delegate: address, expiration: uint256): nonpayable
    # def stake_deposit(sender: address, amount: uint256): nonpayable
    # def stake_withdraw(sender: address, recepient: address, amount: uint256): nonpayable
    # def stake_claim(sender: address, recepient: address): nonpayable

interface ERC721Receiver:
    def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4: view


# Structs

struct TokenContext:
    token_id: uint256
    active_rental: Rental

struct Rental:
    id: bytes32 # keccak256 of the renter, token_id, start and expiration
    owner: address
    renter: address
    delegate: address
    token_id: uint256
    start: uint256
    min_expiration: uint256
    expiration: uint256
    amount: uint256
    protocol_fee: uint256
    protocol_wallet: address

struct Listing:
    token_id: uint256
    price: uint256 # price per hour, 0 means not listed
    min_duration: uint256 # min duration in hours
    max_duration: uint256 # max duration in hours, 0 means unlimited
    timestamp: uint256

struct SignedListings:
    listings: DynArray[Listing, 32]
    v: uint256
    r: uint256
    s: uint256

struct RentalLog:
    id: bytes32
    vault: address
    owner: address
    token_id: uint256
    start: uint256
    min_expiration: uint256
    expiration: uint256
    amount: uint256
    protocol_fee: uint256
    protocol_wallet: address

struct RewardLog:
    vault: address
    token_id: uint256
    amount: uint256
    protocol_fee_amount: uint256
    active_rental_amount: uint256

struct WithdrawalLog:
    vault: address
    token_id: uint256
    rewards: uint256
    protocol_fee_amount: uint256

struct VaultLog:
    vault: address
    token_id: uint256


# Events

event VaultsCreated:
    owner: address
    nft_contract: address
    vaults: DynArray[VaultLog, 32]
    delegate: address

event NftsDeposited:
    owner: address
    nft_contract: address
    vaults: DynArray[VaultLog, 32]
    delegate: address

event NftsWithdrawn:
    owner: address
    nft_contract: address
    total_rewards: uint256
    withdrawals: DynArray[WithdrawalLog, 32]

event DelegatedToWallet:
    owner: address
    delegate: address
    nft_contract: address
    vaults: DynArray[VaultLog, 32]

event ListingsRevoked:
    owner: address
    timestamp: uint256
    token_ids: DynArray[uint256, 32]

event RentalStarted:
    renter: address
    delegate: address
    nft_contract: address
    rentals: DynArray[RentalLog, 32]

event RentalClosed:
    renter: address
    nft_contract: address
    rentals: DynArray[RentalLog, 32]

event RewardsClaimed:
    owner: address
    nft_contract: address
    rewards: DynArray[RewardLog, 32]

event ProtocolFeeSet:
    old_fee: uint256
    new_fee: uint256
    fee_wallet: address

event ProtocolWalletChanged:
    old_wallet: address
    new_wallet: address

event AdminProposed:
    admin: address
    proposed_admin: address

event OwnershipTransferred:
    old_admin: address
    new_admin: address

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    tokenId: indexed(uint256)

event Approval:
    owner: indexed(address)
    approved: indexed(address)
    tokenId: indexed(uint256)

event ApprovalForAll:
    owner: indexed(address)
    operator: indexed(address)
    approved: bool


# Global Variables

_COLLISION_OFFSET: constant(bytes1) = 0xFF
_DEPLOYMENT_CODE: constant(bytes9) = 0x602D3D8160093D39F3
_PRE: constant(bytes10) = 0x363d3d373d3d3d363d73
_POST: constant(bytes15) = 0x5af43d82803e903d91602b57fd5bf3

SUPPORTED_INTERFACES: constant(bytes4[2]) = [0x01ffc9a7, 0x80ac58cd] # ERC165, ERC721

name: constant(String[10]) = ""
symbol: constant(String[4]) = ""

vault_impl_addr: public(immutable(address))
payment_token_addr: public(immutable(address))
nft_contract_addr: public(immutable(address))
delegation_registry_addr: public(immutable(address))
max_protocol_fee: public(immutable(uint256))

protocol_wallet: public(address)
protocol_fee: public(uint256)
protocol_admin: public(address)
proposed_admin: public(address)


active_vaults: public(HashMap[uint256, address]) # token_id -> vault
token_contexts: public(HashMap[uint256, bytes32]) # token_id -> hash(token_context)

id_to_owner: HashMap[uint256, address]
id_to_approvals: HashMap[uint256, address]
id_to_token_count: HashMap[address, uint256]
owner_to_operators: HashMap[address, HashMap[address, bool]]
owner_to_nft_count: HashMap[address, uint256]

unclaimed_rewards: HashMap[address, uint256] # wallet -> amount
protocol_fees_amount: uint256

totalSupply: public(uint256)

##### EXTERNAL METHODS - WRITE #####


@external
def __init__(
    _vault_impl_addr: address,
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address,
    _max_protocol_fee: uint256,
    _protocol_fee: uint256,
    _protocol_wallet: address,
    _protocol_admin: address
):
    vault_impl_addr = _vault_impl_addr
    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    delegation_registry_addr = _delegation_registry_addr
    max_protocol_fee = _max_protocol_fee
    pass




@external
def delegate_to_wallet(token_contexts: DynArray[uint256, 32], delegate: address):
    """
    check if msg.sender is owner and no ongoing rental or msg.sender is current renter
    call vault delegate_to_wallet

    log DelegatedToWallet(msg.sender, delegate, nft_contract_addr, vaults)
    """

@external
def deposit(token_ids: DynArray[uint256, 32], delegate: address):

    """
    _create_vault_if_needed(token_id)
    call vault deposit
    self._addTokenTo(_to, _tokenId)
    self._increaseTotalSupply()

    log NftsDeposited(msg.sender, nft_contract_addr, vault_logs, delegate)
    log Transfer(ZERO_ADDRESS, _to, _tokenId)
    """


@external
def revoke_listing(token_ids: DynArray[uint256, 32]):

    """
    listing_rovocations[token_id] = block.timestamp
    """

    log ListingsRevoked(msg.sender, block.timestamp, token_ids)


@external
def start_rentals(token_contexts: DynArray[TokenContext, 32], listings: SignedListings, duration: uint256, delegate: address):

    """
    check signer(listings) == tokenid_to_vault[token_id].nft_owner
    check listing.timestamp > revocation_timestamp[token_id]
    check hash(token_context) == token_contexts[token_id]

    _compute_rental_amount(block.timestamp, expiration, state.listing.price)
    _transfer_erc20()

    call id_to_vault[token_id].delegate_to_wallet(token_id, delegate)

    _consolidate_rewards(token_context)

    token_contexts[token_id] = hash(Rental({ ... })

    log RentalStarted(msg.sender, delegate, nft_contract_addr, rental_logs)
    """


@external
def close_rentals(token_contexts: DynArray[TokenContext, 32]):

    """
    check hash(token_context) == token_contexts[token_id]
    check if there's an active rental

    unclaimed_rewards[owner] += pro_rata_rental_amount - protocol_fee_amount

    call id_to_vault[token_id].delegate_to_wallet(token_id, empty(address))

    token_contexts[token_id] = hash(Rental({ ... })

    log RentalClosed(msg.sender, nft_contract_addr, rental_logs)
    """


@external
def withdraw(token_contexts: DynArray[TokenContext, 32]):
    """
    check hash(token_context) == token_contexts[token_id]
    check there's no ongoing rental

    _consolidate_rewards(token_context)

    call tokenid_to_vault[token_id].withdraw(msg.sender)

    token_contexts[token_id] = hash(Rental({ ... })

    self._clearApproval(owner, _tokenId)
    self._removeTokenFrom(owner, _tokenId)
    self._decreaseTotalSupply()

    log NftsWithdrawn(msg.sender, nft_contract_addr, withdrawal_log)
    log Transfer(owner, ZERO_ADDRESS, _tokenId)
    """




@external
def claim():
    """
    transfer unclaimed_rewards[msg.sender]
    """

@external
def claim_fees():
    """
    transfer protocol_fees_amount
    """

@external
def set_protocol_fee(protocol_fee: uint256):

    """
    """
    log ProtocolFeeSet(self.protocol_fee, protocol_fee, self.protocol_wallet)



@external
def change_protocol_wallet(new_protocol_wallet: address):

    """
    """
    log ProtocolWalletChanged(self.protocol_wallet, new_protocol_wallet)


@external
def propose_admin(_address: address):

    """
    """
    log AdminProposed(self.protocol_admin, _address)


@external
def claim_ownership():

    """
    """
    log OwnershipTransferred(self.protocol_admin, self.proposed_admin)


@view
@external
def tokenid_to_vault(token_id: uint256) -> address:

    """
    """
    return empty(address)


@view
@external
def is_vault_available(token_id: uint256) -> bool:
    return self.id_to_owner[token_id] == ZERO_ADDRESS

# ERC721

@pure
@external
def supportsInterface(interface_id: bytes4) -> bool:
    return interface_id in SUPPORTED_INTERFACES

@view
@external
def balanceOf(_owner: address) -> uint256:
    assert _owner != ZERO_ADDRESS
    return self.owner_to_nft_count[_owner]


@view
@external
def ownerOf(_tokenId: uint256) -> address:
    owner: address = self.id_to_owner[_tokenId]
    assert owner != ZERO_ADDRESS
    return owner


@view
@external
def getApproved(_tokenId: uint256) -> address:
    assert self.id_to_owner[_tokenId] != ZERO_ADDRESS
    return self.id_to_approvals[_tokenId]


@view
@external
def isApprovedForAll(_owner: address, _operator: address) -> bool:
    return self.owner_to_operators[_owner][_operator]


@external
def transferFrom(_from: address, _to: address, _tokenId: uint256):
    self._transferFrom(_from, _to, _tokenId, msg.sender)


@external
def safeTransferFrom(_from: address, _to: address, _tokenId: uint256, _data: Bytes[1024]=b""):
    self._transferFrom(_from, _to, _tokenId, msg.sender)
    if _to.is_contract:
        returnValue: bytes4 = ERC721Receiver(_to).onERC721Received(msg.sender, _from, _tokenId, _data)
        assert returnValue == convert(method_id("onERC721Received(address,address,uint256,bytes)", output_type=Bytes[4]), bytes4)


@external
def approve(_approved: address, _tokenId: uint256):
    owner: address = self.id_to_owner[_tokenId]
    assert owner != ZERO_ADDRESS
    assert _approved != owner
    assert (self.id_to_owner[_tokenId] == msg.sender or self.owner_to_operators[owner][msg.sender])
    self.id_to_approvals[_tokenId] = _approved
    log Approval(owner, _approved, _tokenId)


@external
def setApprovalForAll(_operator: address, _approved: bool):
    assert _operator != msg.sender
    self.owner_to_operators[msg.sender][_operator] = _approved
    log ApprovalForAll(msg.sender, _operator, _approved)


@view
@external
def tokenURI(tokenId: uint256) -> String[132]:
    return ""


@view
@internal
def _isApprovedOrOwner(_spender: address, _tokenId: uint256) -> bool:
    return False


@internal
def _addTokenTo(_to: address, _tokenId: uint256):
    pass



@internal
def _removeTokenFrom(_from: address, _tokenId: uint256):
    pass


@internal
def _clearApproval(_owner: address, _tokenId: uint256):
    pass


@internal
def _transferFrom(_from: address, _to: address, _tokenId: uint256, _sender: address):
    pass


@internal
def _increaseTotalSupply():
    self.totalSupply += 1


@internal
def _decreaseTotalSupply():
    self.totalSupply -= 1

@internal
def _create_vault_if_needed(token_id: uint256):
    """
    log VaultsCreated(msg.sender, nft_contract_addr, vault_logs, delegate)
    """
