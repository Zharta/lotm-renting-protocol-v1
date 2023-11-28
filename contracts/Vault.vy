# @version 0.3.9

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721

interface IDelegationRegistry:
    def getHotWallet(cold_wallet: address) -> address: view
    def setHotWallet(hot_wallet_address: address, expiration_timestamp: uint256, lock_hot_wallet_address: bool): nonpayable
    def setExpirationTimestamp(expiration_timestamp: uint256): nonpayable


# Structs

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

struct VaultState:
    active_rental: Rental
    listing: Listing


# Global Variables

empty_state_hash: immutable(bytes32)

owner: public(address)
caller: public(address)
state: public(bytes32)
unclaimed_rewards: public(uint256)
unclaimed_protocol_fee: public(uint256)

payment_token_addr: public(immutable(address))
nft_contract_addr: public(immutable(address))
delegation_registry_addr: public(immutable(address))


##### EXTERNAL METHODS - WRITE #####

@payable
@external
def __init__(
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address
):
    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    delegation_registry_addr = _delegation_registry_addr
    empty_state_hash = self._state_hash(empty(VaultState))


@external
def initialise(owner: address):
    assert not self._is_initialised(), "already initialised"

    if self.caller != empty(address):
        assert msg.sender == self.caller, "not caller"
    else:
        self.caller = msg.sender

    self.owner = owner
    self.state = empty_state_hash


@external
def deposit(token_id: uint256, price: uint256, min_duration: uint256, max_duration: uint256, delegate: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert self.state == empty_state_hash, "invalid state"

    if max_duration != 0 and min_duration > max_duration:
        raise "min duration > max duration"

    self.state = self._state_hash2(
        Listing(
            {
                token_id: token_id,
                price: price,
                min_duration: min_duration,
                max_duration: max_duration
            }
        ),
        empty(Rental)
    )

    # transfer token to this contract
    IERC721(nft_contract_addr).safeTransferFrom(self.owner, self, token_id, b"")

    # create delegation
    if delegate != empty(address):
        self._delegate_to_wallet(delegate)


@external
def set_listing(state: VaultState, token_id: uint256, sender: address, price: uint256, min_duration: uint256, max_duration: uint256, delegate: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self.state == self._state_hash(state), "invalid state"
    assert state.listing.token_id == token_id, "invalid token_id"

    self._set_listing(token_id, sender, price, min_duration, max_duration, state.active_rental)

    # create delegation
    if delegate != empty(address):
        self._delegate_to_wallet(delegate)


@external
def start_rental(state: VaultState, renter: address, expiration: uint256, delegate: address, protocol_fee: uint256, protocol_wallet: address) -> Rental:
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert state.listing.price > 0, "listing does not exist"
    assert state.active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self._is_within_duration_range(state.listing, block.timestamp, expiration), "duration not respected"
    assert delegate != empty(address), "delegate is zero address"
    assert self.state == self._state_hash(state), "invalid state"

    rental_amount: uint256 = self._compute_rental_amount(block.timestamp, expiration, state.listing.price)
    assert IERC20(payment_token_addr).allowance(renter, self) >= rental_amount, "insufficient allowance"

    # transfer rental amount from renter to this contract
    assert IERC20(payment_token_addr).transferFrom(renter, self, rental_amount), "transferFrom failed"

    # create delegation
    if IDelegationRegistry(delegation_registry_addr).getHotWallet(self) == delegate:
        IDelegationRegistry(delegation_registry_addr).setExpirationTimestamp(expiration)
    else:
        IDelegationRegistry(delegation_registry_addr).setHotWallet(delegate, expiration, False)

    # store unclaimed rewards
    self._consolidate_claims(state)

    # create rental
    rental_id: bytes32 = self._compute_rental_id(renter, state.listing.token_id, block.timestamp, expiration)
    new_rental: Rental = Rental({
        id: rental_id,
        owner: self.owner,
        renter: renter,
        delegate: delegate,
        token_id: state.listing.token_id,
        start: block.timestamp,
        min_expiration: block.timestamp + state.listing.min_duration * 3600,
        expiration: expiration,
        amount: rental_amount,
        protocol_fee: protocol_fee,
        protocol_wallet: protocol_wallet
    })

    self.state = self._state_hash2(state.listing, new_rental)

    return new_rental


@external
def close_rental(state: VaultState, sender: address) -> uint256:
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert self.state == self._state_hash(state), "invalid state"

    assert state.active_rental.expiration > block.timestamp, "active rental does not exist"
    assert sender == state.active_rental.renter, "not renter of active rental"

    # compute amount to send back to renter
    real_expiration_adjusted: uint256 = block.timestamp
    if block.timestamp < state.active_rental.min_expiration:
        real_expiration_adjusted = state.active_rental.min_expiration

    pro_rata_rental_amount: uint256 = self._compute_real_rental_amount(
        state.active_rental.expiration - state.active_rental.start,
        real_expiration_adjusted - state.active_rental.start,
        state.active_rental.amount
    )
    payback_amount: uint256 = state.active_rental.amount - pro_rata_rental_amount

    protocol_fee_amount: uint256 = pro_rata_rental_amount * state.active_rental.protocol_fee / 10000

    # clear active rental
    self.state = self._state_hash2(state.listing, empty(Rental))

    # set unclaimed rewards
    self.unclaimed_rewards += pro_rata_rental_amount - protocol_fee_amount

    # clear unclaimed protocol fee
    protocol_fee_amount += self.unclaimed_protocol_fee
    self.unclaimed_protocol_fee = 0

    # revoke delegation
    IDelegationRegistry(delegation_registry_addr).setHotWallet(empty(address), 0, False)

    # transfer unused payment to renter
    assert IERC20(payment_token_addr).transfer(state.active_rental.renter, payback_amount), "transfer failed"
    
    # transfer protocol fee to protocol wallet
    if protocol_fee_amount > 0:
        assert IERC20(payment_token_addr).transfer(state.active_rental.protocol_wallet, protocol_fee_amount), "transfer failed"

    return pro_rata_rental_amount


@external
def claim(state: VaultState, sender: address) -> (Rental, uint256, uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self.state == self._state_hash(state), "invalid state"
    assert self._claimable_rewards(state.active_rental) > 0, "no rewards to claim"

    # consolidate last renting rewards if existing
    result_active_rental: Rental = self._consolidate_claims(state)

    rewards_to_claim: uint256 = self.unclaimed_rewards
    protocol_fee_to_claim: uint256 = self.unclaimed_protocol_fee

    # clear unclaimed rewards and protocol fee
    self.unclaimed_rewards = 0
    self.unclaimed_protocol_fee = 0

    # transfer reward to nft owner
    assert IERC20(payment_token_addr).transfer(self.owner, rewards_to_claim), "transfer failed"

    # transfer protocol fee to protocol wallet
    if protocol_fee_to_claim > 0:
        assert IERC20(payment_token_addr).transfer(state.active_rental.protocol_wallet, protocol_fee_to_claim), "transfer failed"

    return result_active_rental, rewards_to_claim, protocol_fee_to_claim


@external
def withdraw(state: VaultState, sender: address) -> (uint256, uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert state.active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self.state == self._state_hash(state), "invalid state"

    # consolidate last renting rewards if existing
    rental: Rental = self._consolidate_claims(state)

    rewards_to_claim: uint256 = self.unclaimed_rewards
    protocol_fee_to_claim: uint256 = self.unclaimed_protocol_fee
    owner: address = self.owner

    # clear vault and set state to zero to uninitialize
    self.unclaimed_rewards = 0
    self.unclaimed_protocol_fee = 0
    self.state = empty(bytes32)
    self.owner = empty(address)

    # transfer token to owner
    IERC721(nft_contract_addr).safeTransferFrom(self, owner, state.listing.token_id, b"")

    # transfer unclaimed rewards to owner
    if rewards_to_claim > 0:
        assert IERC20(payment_token_addr).transfer(owner, rewards_to_claim), "transfer failed"
    
    # transfer protocol fee to protocol wallet
    if protocol_fee_to_claim > 0:
        assert IERC20(payment_token_addr).transfer(state.active_rental.protocol_wallet, protocol_fee_to_claim), "transfer failed"

    return rewards_to_claim, protocol_fee_to_claim


@external
def delegate_to_wallet(state: VaultState, sender: address, delegate: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert state.active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self.state == self._state_hash(state), "invalid state"

    self._delegate_to_wallet(delegate)


##### INTERNAL METHODS #####

@internal
def _consolidate_claims(state: VaultState) -> Rental:
    if state.active_rental.amount == 0 or state.active_rental.expiration >= block.timestamp:
        return state.active_rental
    else:
        protocol_fee_amount: uint256 = state.active_rental.amount * state.active_rental.protocol_fee / 10000

        self.unclaimed_rewards += state.active_rental.amount - protocol_fee_amount
        self.unclaimed_protocol_fee += protocol_fee_amount

        new_rental: Rental = Rental({
            id: state.active_rental.id,
            owner: state.active_rental.owner,
            renter: state.active_rental.renter,
            delegate: state.active_rental.delegate,
            token_id: state.active_rental.token_id,
            start: state.active_rental.start,
            min_expiration: state.active_rental.min_expiration,
            expiration: state.active_rental.expiration,
            amount: 0,
            protocol_fee: state.active_rental.protocol_fee,
            protocol_wallet: state.active_rental.protocol_wallet
        })
        self.state = self._state_hash2(state.listing, new_rental)

        return new_rental

@internal
def _is_within_duration_range(listing: Listing, start: uint256, expiration: uint256) -> bool:
    return expiration - start >= listing.min_duration * 3600 and (listing.max_duration == 0 or expiration - start <= listing.max_duration * 3600)


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


@view
@internal
def _claimable_rewards(active_rental: Rental) -> uint256:
    # protocol_fee_enabled: bool = self.protocol_fee_enabled
    #  protocol_fee: uint256 = self.protocol_fee
    
    if active_rental.expiration < block.timestamp:
        return self.unclaimed_rewards + active_rental.amount * (10000 - active_rental.protocol_fee) / 10000
    else:
        return self.unclaimed_rewards * (10000 - active_rental.protocol_fee) / 10000

@internal
def _delegate_to_wallet(wallet: address):
    delegation_registry: IDelegationRegistry = IDelegationRegistry(delegation_registry_addr)
    if delegation_registry.getHotWallet(self) != wallet:
        delegation_registry.setHotWallet(wallet, max_value(uint256), False)


@internal
def _set_listing(token_id: uint256, sender: address, price: uint256, min_duration: uint256, max_duration: uint256, active_rental: Rental):
    if max_duration != 0 and min_duration > max_duration:
        raise "min duration > max duration"

    self.state = self._state_hash2(
        Listing(
            {
                token_id: token_id,
                price: price,
                min_duration: min_duration,
                max_duration: max_duration
            }
        ),
        active_rental
    )

@pure
@internal
def _state_hash(state: VaultState) -> bytes32:
    return self._state_hash2(state.listing, state.active_rental)

@pure
@internal
def _state_hash2(listing: Listing, rental: Rental) -> bytes32:
    return keccak256(
        concat(
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
            convert(listing.token_id, bytes32),
            convert(listing.price, bytes32),
            convert(listing.min_duration, bytes32),
            convert(listing.max_duration, bytes32),
        )
    )


@view
@internal
def _is_initialised() -> bool:
    return self.state != empty(bytes32)


##### EXTERNAL METHODS - VIEW #####

@view
@external
def claimable_rewards(active_rental: Rental) -> uint256:
    return self._claimable_rewards(active_rental)


@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)

@view
@external
def is_initialised() -> bool:
    return self._is_initialised()
