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

event NFTDeposited:
    owner: address
    token_id: uint256

event NFTWithdrawn:
    owner: address
    token_id: uint256
    claimed_rewards: uint256

event ListingCreated:
    owner: address
    token_id: uint256
    price: uint256

event ListingPriceChanged:
    owner: address
    token_id: uint256
    price: uint256

event ListingCancelled:
    owner: address
    token_id: uint256

event RentalStarted:
    id: bytes32
    owner: address
    renter: address
    token_id: uint256
    start: uint256
    expiration: uint256
    amount: uint256

event RentalClosedPrematurely:
    id: bytes32
    owner: address
    renter: address
    token_id: uint256
    start: uint256
    expiration: uint256
    amount: uint256

event RewardsClaimed:
    owner: address
    token_id: uint256
    amount: uint256


# Structs

struct Rental:
    id: bytes32 # keccak256 of the renter, token_id, start and expiration
    renter: address
    token_id: uint256
    start: uint256
    expiration: uint256
    amount: uint256
    

struct Listing:
    token_id: uint256
    price: uint256 # price per hour
    is_active: bool


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


@view
@external
def aux(tmp: DynArray[uint256, 2**5]) -> (uint256, bool):
    return 1, False


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
def deposit(token_id: uint256):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert IERC721(self.nft_contract_addr).ownerOf(token_id) == self.owner, "not owner of token"
    assert IERC721(self.nft_contract_addr).getApproved(token_id) == self, "not approved for token"

    self.listing = Listing({
        token_id: token_id,
        price: 0,
        is_active: False
    })

    # transfer token to this contract
    IERC721(self.nft_contract_addr).safeTransferFrom(self.owner, self, token_id, b"")

    log NFTDeposited(
        self.owner,
        token_id
    )


@external
def create_listing(sender: address, price: uint256):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert price > 0, "price must be greater than 0"
    assert not self.listing.is_active, "listing already exists"

    self.listing.price = price
    self.listing.is_active = True

    log ListingCreated(
        self.owner,
        self.listing.token_id,
        price
    )


@external
def change_listing_price(sender: address, price: uint256):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert price > 0, "price must be greater than 0"
    assert self.listing.is_active, "listing does not exist"

    self.listing.price = price

    log ListingPriceChanged(
        self.owner,
        self.listing.token_id,
        price
    )


@external
def cancel_listing(sender: address):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self.listing.is_active, "listing does not exist"

    log ListingCancelled(
        self.owner,
        self.listing.token_id
    )

    self.listing = empty(Listing)


@external
def start_rental(renter: address, expiration: uint256):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert self.listing.is_active, "listing does not exist"
    assert self.active_rental.expiration < block.timestamp, "active rental ongoing"

    rental_amount: uint256 = self._compute_rental_amount(block.timestamp, expiration, self.listing.price)
    assert IERC20(self.payment_token_addr).allowance(renter, self) >= rental_amount, "insufficient allowance"

    # store unclaimed rewards
    self.unclaimed_rewards = self.active_rental.amount

    # create rental
    rental_id: bytes32 = self._compute_rental_id(renter, self.listing.token_id, block.timestamp, expiration)
    self.active_rental = Rental({
        id: rental_id,
        renter: renter,
        token_id: self.listing.token_id,
        start: block.timestamp,
        expiration: expiration,
        amount: rental_amount
    })

    # create delegation
    if IDelegationRegistry(self.delegation_registry_addr).getHotWallet(self) == renter:
        IDelegationRegistry(self.delegation_registry_addr).setExpirationTimestamp(expiration)
    else:
        IDelegationRegistry(self.delegation_registry_addr).setHotWallet(renter, expiration, False)
    
    # transfer rental amount from renter to this contract
    IERC20(self.payment_token_addr).transferFrom(renter, self, rental_amount)

    log RentalStarted(
        rental_id,
        self.owner,
        renter,
        self.listing.token_id,
        block.timestamp,
        expiration,
        rental_amount
    )


@external
def close_rental(sender: address):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert self.active_rental.expiration >= block.timestamp, "active rental does not exist"
    assert sender == self.active_rental.renter, "not renter of active rental"
    
    # compute amount to send back to renter
    pro_rata_rental_amount: uint256 = self._compute_rental_amount(self.active_rental.start, block.timestamp, self.listing.price)
    payback_amount: uint256 = self.active_rental.amount - pro_rata_rental_amount

    # clear active rental
    self.active_rental.expiration = block.timestamp
    self.active_rental.amount = pro_rata_rental_amount

    # set unclaimed rewards
    self.unclaimed_rewards = pro_rata_rental_amount

    # revoke delegation
    IDelegationRegistry(self.delegation_registry_addr).renounceHotWallet()

    # transfer unused payment to renter
    IERC20(self.payment_token_addr).transfer(self.active_rental.renter, payback_amount)

    log RentalClosedPrematurely(
        self.active_rental.id,
        self.owner,
        self.active_rental.renter,
        self.listing.token_id,
        self.active_rental.start,
        block.timestamp,
        pro_rata_rental_amount
    )


@external
def claim(sender: address):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self._claimable_rewards() > 0, "no rewards to claim"

    rewards_to_claim: uint256 = self._claimable_rewards()

    # clear uncclaimed rewards
    self.unclaimed_rewards = 0

    # clear active rental if time passed
    if self.active_rental.expiration < block.timestamp:
        self.active_rental.amount = 0

    # transfer reward to nft owner
    IERC20(self.payment_token_addr).transfer(self.active_rental.renter, rewards_to_claim)

    log RewardsClaimed(
        self.owner,
        self.listing.token_id,
        rewards_to_claim
    )


@external
def withdraw(sender: address):
    assert self.is_initialised, "not initialised"
    assert msg.sender == self.caller, "not caller"
    assert sender == self.owner, "not owner of vault"
    assert self.active_rental.expiration < block.timestamp, "active rental ongoing"
    # assert IERC721(self.nft_contract_addr).ownerOf(self.listing.token_id) == self, "not owner of token"
    
    rewards_to_claim: uint256 = self._claimable_rewards()
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
    
    log NFTWithdrawn(
        owner,
        token_id,
        rewards_to_claim
    )


##### INTERNAL METHODS #####

@pure
@internal
def _compute_rental_id(renter: address, token_id: uint256, start: uint256, expiration: uint256) -> bytes32:
    return keccak256(concat(convert(renter, bytes32), convert(token_id, bytes32), convert(start, bytes32), convert(expiration, bytes32)))


@pure
@internal
def _compute_rental_amount(start: uint256, expiration: uint256, price: uint256) -> uint256:
    return (expiration - start) * price / 3600


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
