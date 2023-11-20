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
    token_id: uint256
    start: uint256
    min_expiration: uint256
    expiration: uint256
    amount: uint256


struct Listing:
    token_id: uint256
    price: uint256 # price per hour, 0 means not listed
    min_duration: uint256 # min duration in hours
    max_duration: uint256 # max duration in hours, 0 means unlimited


# Global Variables

empty_rental_hash: immutable(bytes32)
empty_listing_hash: immutable(bytes32)

owner: public(address)
caller: public(address)
listing: public(bytes32)
active_rental: public(bytes32)
unclaimed_rewards: public(uint256)

payment_token_addr: public(address)
nft_contract_addr: public(address)
delegation_registry_addr: public(address)


##### EXTERNAL METHODS - WRITE #####

@payable
@external
def __init__():
    empty_rental_hash = self._rental_hash(empty(Rental))
    empty_listing_hash = self._listing_hash(empty(Listing))


@external
def initialise(
    owner: address,
    payment_token_addr: address,
    nft_contract_addr: address,
    delegation_registry_addr: address
):
    assert not self._is_initialised(), "already initialised"

    if self.caller != empty(address):
        assert msg.sender == self.caller, "not caller"
    else:
        self.caller = msg.sender

    self.owner = owner
    self.listing = empty_listing_hash
    self.active_rental = empty_rental_hash

    self.payment_token_addr = payment_token_addr
    self.nft_contract_addr = nft_contract_addr
    self.delegation_registry_addr = delegation_registry_addr


@external
def deposit(token_id: uint256, price: uint256, min_duration: uint256, max_duration: uint256, delegate: bool):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"

    if max_duration != 0 and min_duration > max_duration:
        raise "min duration > max duration"

    self.listing = self._listing_hash(
        Listing(
            {
                token_id: token_id,
                price: price,
                min_duration: min_duration,
                max_duration: max_duration
            }
        )
    )

    # transfer token to this contract
    IERC721(self.nft_contract_addr).safeTransferFrom(self.owner, self, token_id, b"")

    # create delegation
    if delegate:
        self._delegate_to_owner()


@external
def set_listing(token_id: uint256, sender: address, price: uint256, min_duration: uint256, max_duration: uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"

    self._set_listing(token_id, sender, price, min_duration, max_duration)


@external
def set_listing_and_delegate_to_owner(active_rental: Rental, token_id: uint256, sender: address, price: uint256, min_duration: uint256, max_duration: uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self.active_rental == self._rental_hash(active_rental), "invalid rental"

    self._set_listing(token_id, sender, price, min_duration, max_duration)
    self._delegate_to_owner()


@external
def start_rental(listing: Listing, active_rental: Rental, renter: address, expiration: uint256) -> Rental:
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert listing.price > 0, "listing does not exist"
    assert active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self._is_within_duration_range(listing, block.timestamp, expiration), "duration not respected"
    assert self.listing == self._listing_hash(listing), "invalid listing"
    assert self.active_rental == self._rental_hash(active_rental), "invalid rental"

    rental_amount: uint256 = self._compute_rental_amount(block.timestamp, expiration, listing.price)
    assert IERC20(self.payment_token_addr).allowance(renter, self) >= rental_amount, "insufficient allowance"

    # transfer rental amount from renter to this contract
    assert IERC20(self.payment_token_addr).transferFrom(renter, self, rental_amount), "transferFrom failed"

    # create delegation
    if IDelegationRegistry(self.delegation_registry_addr).getHotWallet(self) == renter:
        IDelegationRegistry(self.delegation_registry_addr).setExpirationTimestamp(expiration)
    else:
        IDelegationRegistry(self.delegation_registry_addr).setHotWallet(renter, expiration, False)

    # store unclaimed rewards
    self._consolidate_claims(active_rental)

    # create rental
    rental_id: bytes32 = self._compute_rental_id(renter, listing.token_id, block.timestamp, expiration)
    new_rental: Rental = Rental({
        id: rental_id,
        owner: self.owner,
        renter: renter,
        token_id: listing.token_id,
        start: block.timestamp,
        min_expiration: block.timestamp + listing.min_duration * 3600,
        expiration: expiration,
        amount: rental_amount
    })

    self.active_rental = self._rental_hash(new_rental)

    return new_rental


@external
def close_rental(rental: Rental, sender: address) -> uint256:
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert self.active_rental == self._rental_hash(rental), "invalid rental"

    assert rental.expiration > block.timestamp, "active rental does not exist"
    assert sender == rental.renter, "not renter of active rental"

    # compute amount to send back to renter
    real_expiration_adjusted: uint256 = block.timestamp
    if block.timestamp < rental.min_expiration:
        real_expiration_adjusted = rental.min_expiration
    pro_rata_rental_amount: uint256 = self._compute_real_rental_amount(
        rental.expiration - rental.start,
        real_expiration_adjusted - rental.start,
        rental.amount
    )
    payback_amount: uint256 = rental.amount - pro_rata_rental_amount

    # clear active rental
    self.active_rental = empty_rental_hash

    # set unclaimed rewards
    self.unclaimed_rewards += pro_rata_rental_amount

    # revoke delegation
    IDelegationRegistry(self.delegation_registry_addr).setHotWallet(empty(address), 0, False)

    # transfer unused payment to renter
    assert IERC20(self.payment_token_addr).transfer(rental.renter, payback_amount), "transfer failed"

    return pro_rata_rental_amount


@external
def claim(active_rental: Rental, sender: address) -> (Rental, uint256):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self.active_rental == self._rental_hash(active_rental), "invalid rental"
    assert self._claimable_rewards(active_rental) > 0, "no rewards to claim"

    # consolidate last renting rewards if existing
    result_active_rental: Rental = self._consolidate_claims(active_rental)

    rewards_to_claim: uint256 = self.unclaimed_rewards

    # clear uncclaimed rewards
    self.unclaimed_rewards = 0

    # transfer reward to nft owner
    assert IERC20(self.payment_token_addr).transfer(active_rental.owner, rewards_to_claim), "transfer failed"

    return result_active_rental, rewards_to_claim


@external
def withdraw(listing: Listing, active_rental: Rental, sender: address) -> uint256:
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self.listing == self._listing_hash(listing), "invalid listing"
    assert self.active_rental == self._rental_hash(active_rental), "invalid rental"

    # consolidate last renting rewards if existing
    self._consolidate_claims(active_rental)

    rewards_to_claim: uint256 = self.unclaimed_rewards
    owner: address = self.owner

    # clear vault and set listing to zero to uninitialize
    self.unclaimed_rewards = 0
    self.listing = empty_listing_hash
    self.active_rental = empty_rental_hash
    self.owner = empty(address)

    # transfer token to owner
    IERC721(self.nft_contract_addr).safeTransferFrom(self, owner, listing.token_id, b"")

    # transfer unclaimed rewards to owner
    if rewards_to_claim > 0:
        assert IERC20(self.payment_token_addr).transfer(owner, rewards_to_claim), "transfer failed"

    return rewards_to_claim


@external
def delegate_to_owner(active_rental: Rental, sender: address):
    assert self._is_initialised(), "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self.active_rental == self._rental_hash(active_rental), "invalid rental"

    self._delegate_to_owner()


##### INTERNAL METHODS #####

@internal
def _consolidate_claims(active_rental: Rental) -> Rental:
    if active_rental.expiration < block.timestamp:
        self.unclaimed_rewards += active_rental.amount
        new_rental: Rental = Rental({
            id: active_rental.id,
            owner: self.owner,
            renter: active_rental.renter,
            token_id: active_rental.token_id,
            start: active_rental.start,
            min_expiration: active_rental.min_expiration,
            expiration: active_rental.expiration,
            amount: 0
        })
        self.active_rental = self._rental_hash(new_rental)
        return new_rental

    else:
        return active_rental

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
    if active_rental.expiration < block.timestamp:
        return self.unclaimed_rewards + active_rental.amount
    else:
        return self.unclaimed_rewards

@internal
def _delegate_to_owner():
    delegation_registry: IDelegationRegistry = IDelegationRegistry(self.delegation_registry_addr)
    owner: address = self.owner
    if delegation_registry.getHotWallet(self) != owner:
        delegation_registry.setHotWallet(owner, max_value(uint256), False)


@internal
def _set_listing(token_id: uint256, sender: address, price: uint256, min_duration: uint256, max_duration: uint256):
    if max_duration != 0 and min_duration > max_duration:
        raise "min duration > max duration"

    self.listing = self._listing_hash(
        Listing(
            {
                token_id: token_id,
                price: price,
                min_duration: min_duration,
                max_duration: max_duration
            }
        )
    )

@pure
@internal
def _listing_hash(listing: Listing) -> bytes32:
    return keccak256(
        concat(
            convert(listing.token_id, bytes32),
            convert(listing.price, bytes32),
            convert(listing.min_duration, bytes32),
            convert(listing.max_duration, bytes32),
        )
    )

@pure
@internal
def _rental_hash(rental: Rental) -> bytes32:
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
        )
    )

@view
@internal
def _is_initialised() -> bool:
    return self.listing != empty(bytes32)


##### EXTERNAL METHODS - VIEW #####

@view
@external
def claimable_rewards(active_rental: Rental) -> uint256:
    assert self.active_rental == self._rental_hash(active_rental), "invalid rental"
    return self._claimable_rewards(active_rental)


@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)

@view
@external
def is_initialised() -> bool:
    return self._is_initialised()
