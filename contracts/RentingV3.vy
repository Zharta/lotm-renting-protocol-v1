# @version 0.3.10

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721

interface ISelf:
    def tokenid_to_vault(token_id: uint256) -> address: view
    def is_vault_available(token_id: uint256) -> bool: view


interface IVault:
    def initialise(staking_pool_id: uint256): nonpayable
    def deposit(token_id: uint256, nft_owner: address, delegate: address): nonpayable
    def withdraw(token_id: uint256, wallet: address): nonpayable
    def delegate_to_wallet(delegate: address, expiration: uint256): nonpayable
    def staking_deposit(sender: address, amount: uint256, token_id: uint256): nonpayable
    def staking_withdraw(wallet: address, amount: uint256, token_id: uint256): nonpayable
    def staking_claim(wallet: address, token_id: uint256): nonpayable
    def staking_compound(wallet: address, token_id: uint256): nonpayable


interface ERC721Receiver:
    def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4: view


# Structs

struct TokenContext:
    token_id: uint256
    nft_owner: address
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

struct Signature:
    v: uint256
    r: uint256
    s: uint256

struct SignedListing:
    listing: Listing
    signature: Signature

struct TokenContextAndListing:
    token_context: TokenContext
    signed_listing: SignedListing

struct TokenContextAndAmount:
    token_context: TokenContext
    amount: uint256

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

struct RentalExtensionLog:
    id: bytes32
    vault: address
    owner: address
    token_id: uint256
    start: uint256
    min_expiration: uint256
    expiration: uint256
    amount_settled: uint256
    extension_amount: uint256
    protocol_fee: uint256
    protocol_wallet: address


struct RewardLog:
    token_id: uint256
    active_rental_amount: uint256

struct WithdrawalLog:
    vault: address
    token_id: uint256
    rewards: uint256
    protocol_fee_amount: uint256

struct VaultLog:
    vault: address
    token_id: uint256

struct StakingLog:
    token_id: uint256
    amount: uint256


# Events

# is this needed?
# event VaultsCreated:
#     owner: address
#     nft_contract: address
#     vaults: DynArray[VaultLog, 32]
#     delegate: address

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

event RentalChanged:
    renter: address
    delegate: address
    nft_contract: address
    rentals: DynArray[RentalLog, 32]

event RentalClosed:
    renter: address
    nft_contract: address
    rentals: DynArray[RentalLog, 32]

event RentalExtended:
    renter: address
    nft_contract: address
    rentals: DynArray[RentalExtensionLog, 32]

event RewardsClaimed:
    owner: address
    amount: uint256
    protocol_fee_amount: uint256
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

event StakingDeposit:
    owner: address
    nft_contract: address
    tokens: DynArray[StakingLog, 32]

event StakingWithdraw:
    owner: address
    nft_contract: address
    recepient: address
    tokens: DynArray[StakingLog, 32]

event StakingClaim:
    owner: address
    nft_contract: address
    recepient: address
    tokens: DynArray[uint256, 32]

event StakingCompound:
    owner: address
    nft_contract: address
    tokens: DynArray[uint256, 32]


# Global Variables

ZHARTA_DOMAIN_NAME: constant(String[6]) = "Zharta"
ZHARTA_DOMAIN_VERSION: constant(String[1]) = "1"

DOMAIN_TYPE_HASH: constant(bytes32) = keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
LISTING_TYPE_HASH: constant(bytes32) = keccak256("Listing(uint256 token_id,uint256 price,uint256 min_duration,uint256 max_duration,uint256 timestamp)")

_COLLISION_OFFSET: constant(bytes1) = 0xFF
_DEPLOYMENT_CODE: constant(bytes9) = 0x602D3D8160093D39F3
_PRE: constant(bytes10) = 0x363d3d373d3d3d363d73
_POST: constant(bytes15) = 0x5af43d82803e903d91602b57fd5bf3

SUPPORTED_INTERFACES: constant(bytes4[2]) = [0x01ffc9a7, 0x80ac58cd] # ERC165, ERC721

name: constant(String[10]) = ""
symbol: constant(String[4]) = ""
listing_sig_domain_separator: immutable(bytes32)
vault_impl_addr: public(immutable(address))
payment_token_addr: public(immutable(address))
nft_contract_addr: public(immutable(address))
delegation_registry_addr: public(immutable(address))
staking_addr: public(immutable(address))
max_protocol_fee: public(immutable(uint256))
staking_pool_id: public(immutable(uint256))

protocol_wallet: public(address)
protocol_fee: public(uint256)
protocol_admin: public(address)
proposed_admin: public(address)

# active_vaults: public(HashMap[uint256, address]) # token_id -> vault

# TODO could this be more efficient using merkle proofs?
rental_states: public(HashMap[uint256, bytes32]) # token_id -> hash(token_context)
listing_revocations: public(HashMap[uint256, uint256]) # token_id -> timestamp

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
    _staking_addr: address,
    _staking_pool_id: uint256,
    _max_protocol_fee: uint256,
    _protocol_fee: uint256,
    _protocol_wallet: address,
    _protocol_admin: address
):
    assert _vault_impl_addr != empty(address), "vault impl is the zero addr"
    assert _payment_token_addr != empty(address), "payment token is the zero addr"
    assert _nft_contract_addr != empty(address), "nft contract is the zero addr"
    assert _delegation_registry_addr != empty(address), "deleg registry is the zero addr"
    # staking_addr can be empty, it's optional
    assert _max_protocol_fee <= 10000, "max protocol fee > 100%"
    assert _protocol_fee <= _max_protocol_fee, "protocol fee > max fee"
    assert _protocol_wallet != empty(address), "protocol wallet not set"
    assert _protocol_admin != empty(address), "admin wallet not set"

    vault_impl_addr = _vault_impl_addr
    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    delegation_registry_addr = _delegation_registry_addr
    staking_addr = _staking_addr
    max_protocol_fee = _max_protocol_fee
    staking_pool_id = _staking_pool_id

    self.protocol_wallet = _protocol_wallet
    self.protocol_fee = _protocol_fee
    self.protocol_admin = _protocol_admin

    listing_sig_domain_separator = keccak256(
        _abi_encode(
            DOMAIN_TYPE_HASH,
            keccak256(ZHARTA_DOMAIN_NAME),
            keccak256(ZHARTA_DOMAIN_VERSION),
            chain.id,
            self
        )
    )



@external
def delegate_to_wallet(token_contexts: DynArray[TokenContext, 32], delegate: address):

    vault_logs: DynArray[VaultLog, 32] = empty(DynArray[VaultLog, 32])

    for token_context in token_contexts:
        assert self._is_context_valid(token_context), "invalid context"
        assert not self._is_rental_active(token_context.active_rental), "active rental"
        assert msg.sender == token_context.nft_owner, "not owner"
        vault: IVault = self._get_vault(token_context.token_id)

        vault.delegate_to_wallet(delegate, 0)

        vault_logs.append(VaultLog({vault: vault.address, token_id: token_context.token_id}))

    log DelegatedToWallet(msg.sender, delegate, nft_contract_addr, vault_logs)



@external
def renter_delegate_to_wallet(token_contexts: DynArray[TokenContext, 32], delegate: address):

    vault_logs: DynArray[VaultLog, 32] = empty(DynArray[VaultLog, 32])

    for token_context in token_contexts:
        assert self._is_context_valid(token_context), "invalid context"
        assert self._is_rental_active(token_context.active_rental), "no active rental"
        assert msg.sender == token_context.active_rental.renter, "not renter"

        vault: IVault = self._get_vault(token_context.token_id)
        vault.delegate_to_wallet(delegate, token_context.active_rental.expiration)

        self._store_token_state(
            token_context.token_id,
            token_context.nft_owner,
            Rental({
                id: token_context.active_rental.id,
                owner: token_context.active_rental.owner,
                renter: token_context.active_rental.renter,
                delegate: delegate,
                token_id: token_context.active_rental.token_id,
                start: token_context.active_rental.start,
                min_expiration: token_context.active_rental.min_expiration,
                expiration: token_context.active_rental.expiration,
                amount: token_context.active_rental.amount,
                protocol_fee: token_context.active_rental.protocol_fee,
                protocol_wallet: token_context.active_rental.protocol_wallet
            })
        )

        vault_logs.append(VaultLog({vault: vault.address, token_id: token_context.token_id}))

    log DelegatedToWallet(msg.sender, delegate, nft_contract_addr, vault_logs)



@external
def deposit(token_ids: DynArray[uint256, 32], delegate: address):

    vault_logs: DynArray[VaultLog, 32] = empty(DynArray[VaultLog, 32])

    for token_id in token_ids:
        assert self.rental_states[token_id] == empty(bytes32), "invalid state"
        vault: IVault = self._create_vault_if_needed(token_id)
        vault.deposit(token_id, msg.sender, delegate)

        self._state_hash(token_id, msg.sender, empty(Rental))
        self._mint_token_to(msg.sender, token_id)

        log Transfer(empty(address), msg.sender, token_id)

        vault_logs.append(VaultLog({
            vault: vault.address,
            token_id: token_id
        }))

    log NftsDeposited(msg.sender, nft_contract_addr, vault_logs, delegate)



@external
def revoke_listing(token_ids: DynArray[uint256, 32]):
    self._revoke_listings(token_ids)
    log ListingsRevoked(msg.sender, block.timestamp, token_ids)


@external
def start_rentals(token_contexts: DynArray[TokenContextAndListing, 32], duration: uint256, delegate: address, signature: Signature):

    signed_listings: DynArray[SignedListing, 32] = empty(DynArray[SignedListing, 32])
    for context in token_contexts:
        signed_listings.append(context.signed_listing)
    assert self._are_listings_signed_by(signed_listings, signature, self.protocol_admin), "invalid signature"

    rental_logs: DynArray[RentalLog, 32] = []
    expiration: uint256 = block.timestamp + duration * 3600

    for context in token_contexts:
        vault: IVault = self._get_vault(context.token_context.token_id)
        assert self._is_context_valid(context.token_context), "invalid context"
        assert not self._is_rental_active(context.token_context.active_rental), "active rental"
        assert self._is_listing_signed_by(context.signed_listing, context.token_context.nft_owner), "invalid signature"
        assert context.signed_listing.listing.timestamp > self.listing_revocations[context.token_context.token_id], "listing revoked"

        rental_amount: uint256 = self._compute_rental_amount(block.timestamp, expiration, context.signed_listing.listing.price)
        self._transfer_erc20(msg.sender, self, rental_amount)

        vault.delegate_to_wallet(delegate, expiration)

        # store unclaimed rewards
        self._consolidate_claims(context.token_context.token_id, context.token_context.nft_owner, context.token_context.active_rental)

        # create rental
        rental_id: bytes32 = self._compute_rental_id(msg.sender, context.token_context.token_id, block.timestamp, expiration)

        new_rental: Rental = Rental({
            id: rental_id,
            owner: context.token_context.nft_owner,
            renter: msg.sender,
            delegate: delegate,
            token_id: context.token_context.token_id,
            start: block.timestamp,
            min_expiration: block.timestamp + context.signed_listing.listing.min_duration * 3600,
            expiration: expiration,
            amount: rental_amount,
            protocol_fee: self.protocol_fee,
            protocol_wallet: self.protocol_wallet
        })

        self._store_token_state(context.token_context.token_id, context.token_context.nft_owner, new_rental)

        rental_logs.append(RentalLog({
            id: rental_id,
            vault: self._tokenid_to_vault(context.token_context.token_id),
            owner: context.token_context.nft_owner,
            token_id: context.token_context.token_id,
            start: block.timestamp,
            min_expiration: new_rental.min_expiration,
            expiration: expiration,
            amount: rental_amount,
            protocol_fee: new_rental.protocol_fee,
            protocol_wallet: new_rental.protocol_wallet
        }))

    log RentalStarted(msg.sender, delegate, nft_contract_addr, rental_logs)



@external
def close_rentals(token_contexts: DynArray[TokenContext, 32]):

    rental_logs: DynArray[RentalLog, 32] = []
    protocol_fees_amount: uint256 = self.protocol_fees_amount
    payback_amounts: uint256 = 0

    for token_context in token_contexts:
        vault: IVault = self._get_vault(token_context.token_id)
        assert self._is_context_valid(token_context), "invalid context"
        assert self._is_rental_active(token_context.active_rental), "active rental does not exist"
        assert msg.sender == token_context.active_rental.renter, "not renter of active rental"

        real_expiration_adjusted: uint256 = block.timestamp
        if block.timestamp < token_context.active_rental.min_expiration:
            real_expiration_adjusted = token_context.active_rental.min_expiration

        pro_rata_rental_amount: uint256 = self._compute_real_rental_amount(
            token_context.active_rental.expiration - token_context.active_rental.start,
            real_expiration_adjusted - token_context.active_rental.start,
            token_context.active_rental.amount
        )
        payback_amount: uint256 = token_context.active_rental.amount - pro_rata_rental_amount
        payback_amounts += payback_amount

        protocol_fee_amount: uint256 = pro_rata_rental_amount * token_context.active_rental.protocol_fee / 10000
        protocol_fees_amount += protocol_fee_amount

        # clear active rental
        self._store_token_state(token_context.token_id, token_context.nft_owner, empty(Rental))

        # set unclaimed rewards
        self.unclaimed_rewards[token_context.nft_owner] += pro_rata_rental_amount - protocol_fee_amount

        # revoke delegation
        vault.delegate_to_wallet(empty(address), 0)

        rental_logs.append(RentalLog({
            id: token_context.active_rental.id,
            vault: vault.address,
            owner: token_context.active_rental.owner,
            token_id: token_context.active_rental.token_id,
            start: token_context.active_rental.start,
            min_expiration: token_context.active_rental.min_expiration,
            expiration: block.timestamp,
            amount: pro_rata_rental_amount,
            protocol_fee: token_context.active_rental.protocol_fee,
            protocol_wallet: token_context.active_rental.protocol_wallet
        }))

    assert IERC20(payment_token_addr).transfer(msg.sender, payback_amounts), "transfer failed"

    if protocol_fees_amount > 0:
        self.protocol_fees_amount = 0
        assert IERC20(payment_token_addr).transfer(self.protocol_wallet, protocol_fees_amount), "transfer failed"

    log RentalClosed(msg.sender, nft_contract_addr, rental_logs)


@external
def extend_rentals(token_contexts: DynArray[TokenContextAndListing, 32], duration: uint256, signature: Signature):

    signed_listings: DynArray[SignedListing, 32] = empty(DynArray[SignedListing, 32])
    for context in token_contexts:
        signed_listings.append(context.signed_listing)
    assert self._are_listings_signed_by(signed_listings, signature, self.protocol_admin), "invalid signature"

    rental_logs: DynArray[RentalExtensionLog, 32] = []
    protocol_fees_amount: uint256 = self.protocol_fees_amount
    payback_amounts: uint256 = 0
    extension_amounts: uint256 = 0
    expiration: uint256 = block.timestamp + duration * 3600

    for context in token_contexts:
        vault: IVault = self._get_vault(context.token_context.token_id)
        assert self._is_context_valid(context.token_context), "invalid context"
        assert not self._is_rental_active(context.token_context.active_rental), "active rental"
        assert msg.sender == context.token_context.active_rental.renter, "not renter of active rental"
        assert self._is_listing_signed_by(context.signed_listing, context.token_context.nft_owner), "invalid signature"
        assert context.signed_listing.listing.timestamp > self.listing_revocations[context.token_context.token_id], "listing revoked"
        assert context.token_context.active_rental.min_expiration <= block.timestamp, "min expiration not reached"

        pro_rata_rental_amount: uint256 = self._compute_real_rental_amount(
            context.token_context.active_rental.expiration - context.token_context.active_rental.start,
            block.timestamp - context.token_context.active_rental.start,
            context.token_context.active_rental.amount
        )
        new_rental_amount: uint256 = self._compute_rental_amount(block.timestamp, expiration, context.signed_listing.listing.price)

        payback_amount: uint256 = context.token_context.active_rental.amount - pro_rata_rental_amount
        payback_amounts += payback_amount

        protocol_fee_amount: uint256 = pro_rata_rental_amount * context.token_context.active_rental.protocol_fee / 10000
        protocol_fees_amount += protocol_fee_amount

        # clear active rental
        self._store_token_state(context.token_context.token_id, context.token_context.nft_owner, empty(Rental))

        # set unclaimed rewards
        self.unclaimed_rewards[context.token_context.nft_owner] += pro_rata_rental_amount - protocol_fee_amount

        # revoke delegation
        vault.delegate_to_wallet(empty(address), 0)

        rental_logs.append(RentalExtensionLog({
            id: context.token_context.active_rental.id,
            vault: vault.address,
            owner: context.token_context.active_rental.owner,
            token_id: context.token_context.active_rental.token_id,
            start: block.timestamp,
            min_expiration: block.timestamp + context.signed_listing.listing.min_duration * 3600,
            expiration: expiration,
            amount_settled: pro_rata_rental_amount,
            extension_amount: new_rental_amount,
            protocol_fee: context.token_context.active_rental.protocol_fee,
            protocol_wallet: context.token_context.active_rental.protocol_wallet
        }))

    if payback_amounts > extension_amounts:
        assert IERC20(payment_token_addr).transfer(msg.sender, payback_amounts - extension_amounts), "transfer failed"
    elif payback_amounts < extension_amounts:
        assert IERC20(payment_token_addr).transfer(self.protocol_wallet, extension_amounts - payback_amounts), "transfer failed"
        self._transfer_erc20(self.protocol_wallet, msg.sender, extension_amounts - payback_amounts)

    if protocol_fees_amount > 0:
        self.protocol_fees_amount = 0
        assert IERC20(payment_token_addr).transfer(self.protocol_wallet, protocol_fees_amount), "transfer failed"

    log RentalExtended(msg.sender, nft_contract_addr, rental_logs)


@external
def withdraw(token_contexts: DynArray[TokenContext, 32]):

    withdrawal_log: DynArray[WithdrawalLog, 32] = empty(DynArray[WithdrawalLog, 32])
    total_rewards: uint256 = 0
    rewards: uint256 = 0
    protocol_fee_amount: uint256 = 0

    for token_context in token_contexts:
        assert self._is_context_valid(token_context), "invalid context"
        assert self.id_to_owner[token_context.token_id] == msg.sender, "not owner"
        assert not self._is_rental_active(token_context.active_rental), "active rental"

        vault: IVault = self._get_vault(token_context.token_id)

        rental: Rental = self._consolidate_claims(token_context.token_id, token_context.nft_owner, token_context.active_rental, False)

        self._clear_token_state(token_context.token_id)

        # TODO should we burn the token?
        self._burn_token_from(msg.sender, token_context.token_id)
        log Transfer(empty(address), msg.sender, token_context.token_id)

        vault.withdraw(token_context.token_id, msg.sender)
        self._revoke_listings([token_context.token_id])

        withdrawal_log.append(WithdrawalLog({
            vault: vault.address,
            token_id: token_context.token_id,
            rewards: rewards,
            protocol_fee_amount: protocol_fee_amount
        }))
        total_rewards += rewards

    rewards_to_claim: uint256 = self.unclaimed_rewards[msg.sender]
    protocol_fee_to_claim: uint256 = self.protocol_fees_amount

    # transfer reward to nft owner
    if rewards_to_claim > 0:
        assert IERC20(payment_token_addr).transfer(msg.sender, rewards_to_claim), "transfer failed"
        self.unclaimed_rewards[msg.sender] = 0

    # transfer protocol fee to protocol wallet
    if protocol_fee_to_claim > 0:
        assert IERC20(payment_token_addr).transfer(self.protocol_wallet, protocol_fee_to_claim), "transfer failed"
        self.protocol_fees_amount = 0

    log NftsWithdrawn(
        msg.sender,
        nft_contract_addr,
        total_rewards,
        withdrawal_log
    )

@external
def stake_deposit(token_contexts: DynArray[TokenContextAndAmount, 32]):
    assert staking_addr != empty(address), "staking not supported"

    staking_log: DynArray[StakingLog, 32] = empty(DynArray[StakingLog, 32])
    total_amount: uint256 = 0
    for context in token_contexts:
        assert msg.sender == context.token_context.nft_owner, "not owner"
        assert self._is_context_valid(context.token_context), "invalid context"
        total_amount += context.amount

    assert IERC20(payment_token_addr).allowance(msg.sender, self) >= total_amount, "insufficient allowance"

    for context in token_contexts:
        vault: IVault = self._get_vault(context.token_context.token_id)
        assert IERC20(payment_token_addr).transferFrom(msg.sender, vault.address, context.amount), "transferFrom failed"
        vault.staking_deposit(msg.sender, context.amount, context.token_context.token_id)
        staking_log.append(StakingLog({
            token_id: context.token_context.token_id,
            amount: context.amount
        }))

    log StakingDeposit(msg.sender, nft_contract_addr, staking_log)


@external
def stake_withdraw(token_contexts: DynArray[TokenContextAndAmount, 32], recepient: address):
    assert staking_addr != empty(address), "staking not supported"

    staking_log: DynArray[StakingLog, 32] = empty(DynArray[StakingLog, 32])

    for context in token_contexts:
        assert msg.sender == context.token_context.nft_owner, "not owner"
        assert self._is_context_valid(context.token_context), "invalid context"

        self._get_vault(context.token_context.token_id).staking_withdraw(recepient, context.amount, context.token_context.token_id)
        staking_log.append(StakingLog({
            token_id: context.token_context.token_id,
            amount: context.amount
        }))

    log StakingWithdraw(msg.sender, nft_contract_addr, recepient, staking_log)


@external
def stake_claim(token_contexts: DynArray[TokenContextAndAmount, 32], recepient: address):
    assert staking_addr != empty(address), "staking not supported"
    tokens: DynArray[uint256, 32] = empty(DynArray[uint256, 32])

    for context in token_contexts:
        assert msg.sender == context.token_context.nft_owner, "not owner"
        assert self._is_context_valid(context.token_context), "invalid context"
        self._get_vault(context.token_context.token_id).staking_claim(recepient, context.token_context.token_id)
        tokens.append(context.token_context.token_id)

    log StakingClaim(msg.sender, nft_contract_addr, recepient, tokens)

@external
def stake_compound(token_contexts: DynArray[TokenContextAndAmount, 32]):
    assert staking_addr != empty(address), "staking not supported"
    tokens: DynArray[uint256, 32] = empty(DynArray[uint256, 32])

    for context in token_contexts:
        assert msg.sender == context.token_context.nft_owner, "not owner"
        assert self._is_context_valid(context.token_context), "invalid context"

        self._get_vault(context.token_context.token_id).staking_compound(msg.sender, context.token_context.token_id)
        tokens.append(context.token_context.token_id)

    log StakingCompound(msg.sender, nft_contract_addr, tokens)


@external
def claim(token_contexts: DynArray[TokenContext, 32]):

    reward_logs: DynArray[RewardLog, 32] = []

    for token_context in token_contexts:
        assert self._is_context_valid(token_context), "invalid context"
        assert token_context.nft_owner == msg.sender, "not owner"

        result_active_rental: Rental = self._consolidate_claims(token_context.token_id, token_context.nft_owner, token_context.active_rental)

        reward_logs.append(RewardLog({
            token_id: token_context.token_id,
            active_rental_amount: result_active_rental.amount
        }))

    rewards_to_claim: uint256 = self.unclaimed_rewards[msg.sender]
    protocol_fee_to_claim: uint256 = self.protocol_fees_amount

    # transfer reward to nft owner
    assert rewards_to_claim > 0, "no rewards to claim"
    assert IERC20(payment_token_addr).transfer(msg.sender, rewards_to_claim), "transfer failed"
    self.unclaimed_rewards[msg.sender] = 0

    # transfer protocol fee to protocol wallet
    if protocol_fee_to_claim > 0:
        assert IERC20(payment_token_addr).transfer(self.protocol_wallet, protocol_fee_to_claim), "transfer failed"
        self.protocol_fees_amount = 0

    log RewardsClaimed(msg.sender, rewards_to_claim, protocol_fee_to_claim, reward_logs)


@external
def claim_fees():
    assert msg.sender == self.protocol_admin, "not admin"
    assert self.protocol_fees_amount > 0, "no fees to claim"
    protocol_fees_amount: uint256 = self.protocol_fees_amount
    self.protocol_fees_amount = 0
    assert IERC20(payment_token_addr).transfer(self.protocol_wallet, protocol_fees_amount), "transfer failed"


@external
def set_protocol_fee(protocol_fee: uint256):
    assert msg.sender == self.protocol_admin, "not protocol admin"
    assert protocol_fee <= max_protocol_fee, "protocol fee > max fee"
    assert protocol_fee != self.protocol_fee, "protocol fee is the same"

    self.protocol_fee = protocol_fee
    log ProtocolFeeSet(self.protocol_fee, protocol_fee, self.protocol_wallet)


@external
def change_protocol_wallet(new_protocol_wallet: address):
    assert msg.sender == self.protocol_admin, "not protocol admin"
    assert new_protocol_wallet != empty(address), "wallet is the zero address"

    self.protocol_wallet = new_protocol_wallet
    log ProtocolWalletChanged(self.protocol_wallet, new_protocol_wallet)


@external
def propose_admin(_address: address):
    assert msg.sender == self.protocol_admin, "not the admin"
    assert _address != empty(address), "_address is the zero address"
    assert self.protocol_admin != _address, "proposed admin addr is the admin"
    assert self.proposed_admin != _address, "proposed admin addr is the same"

    self.proposed_admin = _address
    log AdminProposed(self.protocol_admin, _address)


@external
def claim_ownership():
    assert msg.sender == self.proposed_admin, "not the proposed"
    self.protocol_admin = self.proposed_admin
    self.proposed_admin = empty(address)
    log OwnershipTransferred(self.protocol_admin, self.proposed_admin)


@view
@external
def tokenid_to_vault(token_id: uint256) -> address:
    return self._tokenid_to_vault(token_id)


@view
@external
def is_vault_available(token_id: uint256) -> bool:
    return self.id_to_owner[token_id] == empty(address)

# ERC721

@pure
@external
def supportsInterface(interface_id: bytes4) -> bool:
    return interface_id in SUPPORTED_INTERFACES

@view
@external
def balanceOf(_owner: address) -> uint256:
    assert _owner != empty(address)
    return self.owner_to_nft_count[_owner]


@view
@external
def ownerOf(_tokenId: uint256) -> address:
    owner: address = self.id_to_owner[_tokenId]
    assert owner != empty(address)
    return owner


@view
@external
def getApproved(_tokenId: uint256) -> address:
    assert self.id_to_owner[_tokenId] != empty(address)
    return self.id_to_approvals[_tokenId]


@view
@external
def isApprovedForAll(_owner: address, _operator: address) -> bool:
    return self.owner_to_operators[_owner][_operator]


@external
def transferFrom(_from: address, _to: address, _tokenId: uint256):
    self._transfer_from(_from, _to, _tokenId, msg.sender)


@external
def safeTransferFrom(_from: address, _to: address, _tokenId: uint256, _data: Bytes[1024]=b""):
    self._transfer_from(_from, _to, _tokenId, msg.sender)
    if _to.is_contract:
        returnValue: bytes4 = ERC721Receiver(_to).onERC721Received(msg.sender, _from, _tokenId, _data)
        assert returnValue == convert(method_id("onERC721Received(address,address,uint256,bytes)", output_type=Bytes[4]), bytes4)


@external
def approve(_approved: address, _tokenId: uint256):
    owner: address = self.id_to_owner[_tokenId]
    assert owner != empty(address)
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
def _tokenid_to_vault(token_id: uint256) -> address:
    return self._compute_address(
        convert(token_id, bytes32),
        keccak256(concat(
            _DEPLOYMENT_CODE,
            _PRE,
            convert(vault_impl_addr, bytes20),
            _POST
        )),
        self
    )

@pure
@internal
def _state_hash(token_id: uint256, nft_owner: address, rental: Rental) -> bytes32:
    return keccak256(
        concat(
            convert(token_id, bytes32),
            convert(nft_owner, bytes32),
            rental.id,
            convert(rental.owner, bytes32),
            convert(rental.renter, bytes32),
            convert(rental.token_id, bytes32),
            convert(rental.start, bytes32),
            convert(rental.min_expiration, bytes32),
            convert(rental.expiration, bytes32),
            convert(rental.amount, bytes32),
            convert(rental.protocol_fee, bytes32),
            convert(rental.protocol_wallet, bytes32),
        )
    )

@view
@internal
def _is_approved_or_owner(_spender: address, _token_id: uint256) -> bool:
    owner: address = self.id_to_owner[_token_id]
    return _spender == owner or _spender == self.id_to_approvals[_token_id] or self.owner_to_operators[owner][_spender]


@pure
@internal
def _compute_address(salt: bytes32, bytecode_hash: bytes32, deployer: address) -> address:
    data: bytes32 = keccak256(concat(_COLLISION_OFFSET, convert(deployer, bytes20), salt, bytecode_hash))
    return self._convert_keccak256_2_address(data)


@pure
@internal
def _convert_keccak256_2_address(digest: bytes32) -> address:
    return convert(convert(digest, uint256) & convert(max_value(uint160), uint256), address)


@view
@internal
def _is_rental_active(rental: Rental) -> bool:
    return rental.expiration < block.timestamp


@view
@internal
def _is_context_valid(context: TokenContext) -> bool:
    return self.rental_states[context.token_id] == self._state_hash(context.token_id, context.nft_owner, context.active_rental)


@internal
def _store_token_state(token_id: uint256, nft_owner: address, rental: Rental):
    self.rental_states[token_id] = self._state_hash(token_id, nft_owner, rental)


@internal
def _clear_token_state(token_id: uint256):
    self.rental_states[token_id] = empty(bytes32)


@internal
def _mint_token_to(_to: address, _token_id: uint256):
    self._add_token_to(_to, _token_id)
    self._increase_total_supply()


@internal
def _burn_token_from(_owner: address, _token_id: uint256):
    self._remove_token_from(_owner, _token_id)
    self._decrease_total_supply()


@internal
def _add_token_to(_to: address, _token_id: uint256):
    self.id_to_owner[_token_id] = _to
    self.owner_to_nft_count[_to] += 1


@internal
def _remove_token_from(_from: address, _token_id: uint256):
    self.id_to_owner[_token_id] = empty(address)
    self.owner_to_nft_count[_from] -= 1
    self._clear_approval(_from, _token_id)


@internal
def _clear_approval(_owner: address, _token_id: uint256):
    if self.id_to_approvals[_token_id] != empty(address):
        self.id_to_approvals[_token_id] = empty(address)


@internal
def _transfer_from(_from: address, _to: address, _token_id: uint256, _sender: address):
    assert self._is_approved_or_owner(_sender, _token_id)
    assert _to != empty(address)
    self._clear_approval(_from, _token_id)
    self.id_to_owner[_token_id] = _to
    log Transfer(_from, _to, _token_id)


@internal
def _increase_total_supply():
    self.totalSupply += 1

@internal
def _decrease_total_supply():
    self.totalSupply -= 1


@internal
def _get_vault(token_id: uint256) -> IVault:
    vault: address = self._tokenid_to_vault(token_id)
    assert vault.is_contract, "no vault exists for token_id"
    return IVault(vault)


@internal
def _create_vault_if_needed(token_id: uint256) -> IVault:
    vault: address = self._tokenid_to_vault(token_id)
    if not vault.is_contract:
        vault = create_minimal_proxy_to(vault_impl_addr, salt=convert(token_id, bytes32))
        IVault(vault).initialise(staking_pool_id)
        # log VaultsCreated(msg.sender, nft_contract_addr, vault_logs, delegate)?

    return IVault(vault)


@internal
def _transfer_erc20(_from: address, _to: address, _amount: uint256):
    assert IERC20(payment_token_addr).allowance(_from, self) >= _amount, "insufficient allowance"
    assert IERC20(payment_token_addr).transferFrom(_from, _to, _amount), "transferFrom failed"


@internal
def _revoke_listings(token_ids: DynArray[uint256, 32]):
    for token_id in token_ids:
        assert self.id_to_owner[token_id] == msg.sender, "not owner"
        self.listing_revocations[token_id] = block.timestamp


@pure
@internal
def _compute_rental_id(renter: address, token_id: uint256, start: uint256, expiration: uint256) -> bytes32:
    return keccak256(concat(convert(renter, bytes32), convert(token_id, bytes32), convert(start, bytes32), convert(expiration, bytes32)))

@pure
@internal
def _compute_rental_amount(start: uint256, expiration: uint256, price: uint256) -> uint256:
    return (expiration - start) * price / 3600


@pure
@internal
def _compute_real_rental_amount(duration: uint256, real_duration: uint256, rental_amount: uint256) -> uint256:
    return rental_amount * real_duration / duration

@internal
def _consolidate_claims(token_id: uint256, nft_owner: address, active_rental: Rental, store_state: bool = True) -> Rental:
    if active_rental.amount == 0 or active_rental.expiration >= block.timestamp:
        return active_rental
    else:
        protocol_fee_amount: uint256 = active_rental.amount * active_rental.protocol_fee / 10000

        self.unclaimed_rewards[active_rental.renter] += active_rental.amount - protocol_fee_amount
        self.protocol_fees_amount += protocol_fee_amount

        new_rental: Rental = Rental({
            id: active_rental.id,
            owner: active_rental.owner,
            renter: active_rental.renter,
            delegate: active_rental.delegate,
            token_id: token_id,
            start: active_rental.start,
            min_expiration: active_rental.min_expiration,
            expiration: active_rental.expiration,
            amount: 0,
            protocol_fee: active_rental.protocol_fee,
            protocol_wallet: active_rental.protocol_wallet
        })

        if store_state:
            self._store_token_state(token_id, nft_owner, new_rental)

        return new_rental



@internal
def _is_listing_signed_by(signed_listing: SignedListing, signer: address) -> bool:
    return ecrecover(
        keccak256(
            concat(
                convert("\x19\x01", Bytes[2]),
                _abi_encode(
                    listing_sig_domain_separator,
                    keccak256(_abi_encode(LISTING_TYPE_HASH, signed_listing.listing))
                )
            )
        ),
        signed_listing.signature.v,
        signed_listing.signature.r,
        signed_listing.signature.s
    ) == signer


@internal
def _are_listings_signed_by(signed_listings: DynArray[SignedListing, 32], signature: Signature, signer: address) -> bool:
    return False
