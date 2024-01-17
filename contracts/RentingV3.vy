# @version 0.3.9

# Interfaces

interface IVaultManager:
    def deposit(token_ids: DynArray[uint256, 32], delegate: address): nonpayable
    def withdraw(token_contexts: DynArray[uint256, 32]): nonpayable
    def delegate_to_wallet(token_contexts: DynArray[uint256, 32], delegate: address): nonpayable
    def stake_deposit(token_id: uint256, amount: uint256): nonpayable
    def stake_withdraw(token_id: uint256, recepient: address, amount: uint256): nonpayable
    def stake_claim(token_id: uint256, recepient: address): nonpayable
    def stake_compound(token_id: uint256): nonpayable
    def tokenid_to_vault(token_id: uint256) -> address: view

interface Registry:
    def set_permissions(_contract: address, _permissions_mask: uint256): nonpayable
    def has_permission(_contract: address, _vault_owner: address, _permission: uint256) -> bool: nonpayable
    def set_withdrawal_lock(_token_id: uint256): nonpayable
    def unset_withdrawal_lock(_token_id: uint256): nonpayable
    def set_delegate_lock(_token_id: uint256, _expiration: uint256): nonpayable
    def unset_delegate_lock(_token_id: uint256): nonpayable
    def set_staking_lock(_token_id: uint256, _expiration: uint256, amount: uint256): nonpayable
    def unset_staking_lock(_token_id: uint256): nonpayable
    def set_staking_rewards_lock(_token_id: uint256, _expiration: uint256): nonpayable
    def unset_staking_rewards_lock(_token_id: uint256): nonpayable
    def permissions(arg0: address, arg1: address) -> uint256: view
    def withdrawal_locks(arg0: uint256) -> address: view
    # def delegation_locks(arg0: uint256) -> DelegateLock: view
    # def staking_locks(arg0: uint256) -> StakeLock: view
    # def staking_rewards_locks(arg0: uint256) -> StakeRewardLock: view


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


# Events

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


# Global Variables

vault_manager_addr: public(immutable(address))
payment_token_addr: public(immutable(address))
nft_contract_addr: public(immutable(address))
max_protocol_fee: public(immutable(uint256))

protocol_wallet: public(address)
protocol_fee: public(uint256)
protocol_admin: public(address)
proposed_admin: public(address)

token_contexts: public(HashMap[uint256, bytes32]) # token_id -> hash(token_context)
active_vaults: public(HashMap[uint256, address]) # token_id -> vault


##### EXTERNAL METHODS - WRITE #####

@external
def __init__(
    _vault_manager_addr: address,
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _max_protocol_fee: uint256,
    _protocol_fee: uint256,
    _protocol_wallet: address,
    _protocol_admin: address
):
    vault_manager_addr = _vault_manager_addr
    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    max_protocol_fee = _max_protocol_fee
    pass


@external
def deposit(token_ids: DynArray[uint256, 32], delegate: address):

    """
    call VaultManager.deposit
    call VaultManager.delegate if needed (Q: add delegate param to VaultManager.deposit?)
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
    check signer(listings) == VaultManager.tokenid_to_vault[token_id].nft_owner
    check listing.timestamp > revocation_timestamp[token_id]
    check hash(token_context) == token_contexts[token_id]

    call VaultManager.set_withdrawal_lock(token_id)
    call VaultManager.stack(amount)
    call VaultManager.set_staking_lock(token_id, amount, expiration)
    call VaultManager.stake(amount)
    call VaultManager.delegate_to_wallet(delegate)
    call VaultManager.set_delegate_lock(token_id, expiration)

    token_contexts[token_id] = hash(Rental({ ... })

    log RentalStarted(msg.sender, delegate, nft_contract_addr, rental_logs)
    """


@external
def close_rentals(token_contexts: DynArray[TokenContext, 32]):

    """
    check hash(token_context) == token_contexts[token_id]
    pro_rata_amountal = ....
    payback_amount = ....

    call VaultManager.unset_delegate_lock(token_id)
    call VaultManager.unset_staking_lock(token_id)
    call VaultManager.unset_withdrawal_lock(token_id)

    call VaultManager.stake_withdraw(token_id, msg.sender, payback_amount)
    call VaultManager.delegate_to_wallet(empty(address))
    call VaultManager.set_delegate_lock(token_id, expiration)

    token_contexts[token_id] = hash(Rental({ ... })

    log RentalClosed(msg.sender, nft_contract_addr, rental_logs)
    """




@external
def withdraw(token_contexts: DynArray[TokenContext, 32]):
    """
    check hash(token_context) == token_contexts[token_id]

    call VaultManager.unset_delegate_lock(token_id)
    call VaultManager.unset_staking_lock(token_id)
    call VaultManager.unset_withdrawal_lock(token_id)

    call VaultManager.withdraw(token_contexts)

    token_contexts[token_id] = hash(Rental({ ... })
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
