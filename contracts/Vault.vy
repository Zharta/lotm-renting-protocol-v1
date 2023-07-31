# @version 0.3.9

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721

interface IDelegationRegistry:
    def getHotWallet(cold_wallet: address) -> address: view
    def setHotWallet(hot_wallet_address: address, expiration_timestamp: uint256, lock_hot_wallet_address: bool): nonpayable
    def setExpirationTimestamp(expiration_timestamp: uint256): nonpayable
    def renounceHotWallet(): nonpayable


# Events


# Structs

struct Rental:
    id: bytes32 # keccak256 of the renter, token_id, start and expiration
    owner: address
    renter: address
    token_id: uint256
    start: uint256
    expiration: uint256
    amount: uint256
    

struct Listing:
    token_id: uint256
    price: uint256 # price per hour, 0 means not listed
    max_duration: uint256 # max duration in hours, 0 means unlimited


# Global Variables

is_initialised: public(bool)
owner: public(address)
caller: public(address)
listing: public(Listing)
active_rental: public(Rental)
unclaimed_rewards: public(uint256)

payment_token_addr: public(address)
nft_contract_addr: public(address)
delegation_registry_addr: public(address)


##### EXTERNAL METHODS - WRITE #####

@external
def __init__():
    pass


@external
def initialise(
    owner: address,
    caller: address,
    payment_token_addr: address,
    nft_contract_addr: address,
    delegation_registry_addr: address
):
    assert not self.is_initialised, "already initialised"
    
    self.owner = owner
    self.caller = caller
    self.is_initialised = True

    self.payment_token_addr = payment_token_addr
    self.nft_contract_addr = nft_contract_addr
    self.delegation_registry_addr = delegation_registry_addr


@external
def deposit(token_id: uint256, price: uint256, max_duration: uint256):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert IERC721(self.nft_contract_addr).ownerOf(token_id) == self.owner, "not owner of token"
    assert IERC721(self.nft_contract_addr).getApproved(token_id) == self, "not approved for token"

    self.listing = Listing({
        token_id: token_id,
        price: price,
        max_duration: max_duration
    })

    # transfer token to this contract
    IERC721(self.nft_contract_addr).safeTransferFrom(self.owner, self, token_id, b"")


@external
def set_listing_price(sender: address, price: uint256, max_duration: uint256):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"

    self.listing.price = price
    self.listing.max_duration = max_duration


@external
def start_rental(renter: address, expiration: uint256) -> Rental:
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert self._is_active(), "listing does not exist"
    assert self.active_rental.expiration < block.timestamp, "active rental ongoing"
    assert self._is_within_max_duration(block.timestamp, expiration), "max duration exceeded"

    listing: Listing = self.listing

    rental_amount: uint256 = self._compute_rental_amount(block.timestamp, expiration, listing.price)
    assert IERC20(self.payment_token_addr).allowance(renter, self) >= rental_amount, "insufficient allowance"

    # store unclaimed rewards
    self._consolidate_claims()

    # create rental
    rental_id: bytes32 = self._compute_rental_id(renter, listing.token_id, block.timestamp, expiration)
    self.active_rental = Rental({
        id: rental_id,
        owner: self.owner,
        renter: renter,
        token_id: listing.token_id,
        start: block.timestamp,
        expiration: expiration,
        amount: rental_amount
    })

    # create delegation
    if IDelegationRegistry(self.delegation_registry_addr).getHotWallet(self) == renter:
        IDelegationRegistry(self.delegation_registry_addr).setExpirationTimestamp(expiration)
    else:
        IDelegationRegistry(self.delegation_registry_addr).setHotWallet(renter, expiration, False)
        # TODO can this be used in both cases?
    
    # transfer rental amount from renter to this contract
    IERC20(self.payment_token_addr).transferFrom(renter, self, rental_amount)

    return self.active_rental


@external
def close_rental(sender: address) -> (Rental, uint256):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    
    rental: Rental = self.active_rental

    assert rental.expiration >= block.timestamp, "active rental does not exist"
    assert sender == rental.renter, "not renter of active rental"
    
    # compute amount to send back to renter
    pro_rata_rental_amount: uint256 = self._compute_real_rental_amount(rental.expiration - rental.start, block.timestamp - rental.start, rental.amount)
    payback_amount: uint256 = rental.amount - pro_rata_rental_amount

    # clear active rental
    rental.expiration = block.timestamp
    rental.amount = 0
    self.active_rental = rental

    # set unclaimed rewards
    self.unclaimed_rewards += pro_rata_rental_amount

    # revoke delegation
    IDelegationRegistry(self.delegation_registry_addr).renounceHotWallet()

    # transfer unused payment to renter
    IERC20(self.payment_token_addr).transfer(rental.renter, payback_amount)

    return rental, pro_rata_rental_amount


@external
def claim(sender: address) -> uint256:
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self._claimable_rewards() > 0, "no rewards to claim"

    # consolidate last renting rewards if existing
    self._consolidate_claims()

    rewards_to_claim: uint256 = self.unclaimed_rewards

    # clear uncclaimed rewards
    self.unclaimed_rewards = 0

    # transfer reward to nft owner
    IERC20(self.payment_token_addr).transfer(self.active_rental.owner, rewards_to_claim)

    return rewards_to_claim


@external
def withdraw(sender: address) -> uint256:
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self.active_rental.expiration < block.timestamp, "active rental ongoing"
    
    # consolidate last renting rewards if existing
    self._consolidate_claims()

    rewards_to_claim: uint256 = self.unclaimed_rewards
    token_id: uint256 = self.listing.token_id
    owner: address = self.owner

    # clear vault
    self.unclaimed_rewards = 0
    self.listing = empty(Listing)
    self.active_rental = empty(Rental)
    self.is_initialised = False
    self.owner = empty(address)

    # transfer token to owner
    IERC721(self.nft_contract_addr).safeTransferFrom(self, owner, token_id, b"")

    # transfer unclaimed rewards to owner
    if rewards_to_claim > 0:
        IERC20(self.payment_token_addr).transfer(owner, rewards_to_claim)

    return rewards_to_claim


##### INTERNAL METHODS #####

@internal
def _is_active() -> bool:
    return self.listing.price > 0

@internal
def _consolidate_claims():
    if self.active_rental.expiration < block.timestamp:
        self.unclaimed_rewards += self.active_rental.amount
        self.active_rental.amount = 0

@internal
def _is_within_max_duration(start: uint256, expiration: uint256) -> bool:
    return self.listing.max_duration == 0 or expiration - start <= self.listing.max_duration * 3600


@pure
@internal
def _compute_rental_id(renter: address, token_id: uint256, start: uint256, expiration: uint256) -> bytes32:
    return keccak256(concat(convert(renter, bytes32), convert(token_id, bytes32), convert(start, bytes32), convert(expiration, bytes32)))


@pure
@internal
def _compute_rental_amount(start: uint256, expiration: uint256, price: uint256) -> uint256:
    ## TODO calc uses listing price which can change
    return (expiration - start) * price / 3600


@pure
@internal
def _compute_real_rental_amount(duration: uint256, real_duration: uint256, rental_amount: uint256) -> uint256:
    return rental_amount * real_duration / duration


@view
@internal
def _claimable_rewards() -> uint256:
    if self.active_rental.expiration < block.timestamp:
        return self.unclaimed_rewards + self.active_rental.amount
    else:
        return self.unclaimed_rewards


##### EXTERNAL METHODS - VIEW #####

@view
@external
def claimable_rewards() -> uint256:
    return self._claimable_rewards()


@view
@external
def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
    return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)
